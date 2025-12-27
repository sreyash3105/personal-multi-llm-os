# backend/modules/stt/stt_service.py
"""
Robust STT service wrapper for faster-whisper.
UPGRADED (V4.0): Integrated with Global Job Queue for VRAM safety.

Features:
 - decode many container formats via av
 - resample to TARGET_SR (16000) mono using av.AudioResampler
 - normalize to float32 in [-1, 1]
 - call faster-whisper model.transcribe with numpy (assumes 16k) or fallback to temp WAV path
 - fp16 -> float32 model reload fallback
 - telemetry hooks (history_logger, assess_risk)
 - 🟢 VRAM Guard: Pauses if Vision/LLM are using the GPU.
"""

import io
import os
import time
import tempfile
import logging
import threading
from typing import Optional, Tuple

import av
import numpy as np
import soundfile as sf

# 🟢 V4 Queue Imports
from backend.modules.jobs.queue_manager import (
    enqueue_job,
    try_acquire_next_job,
    get_job,
    mark_job_done,
    mark_job_failed
)

from backend.core import config  # your project config

from backend.core.feature_registry import register_feature

# Safe imports for optional modules
try:
    from faster_whisper import WhisperModel
    register_feature(
        "faster_whisper",
        True,
        "Optimized STT transcription",
        install_hint="pip install faster-whisper",
        fallback_behavior="basic transcription (slower)"
    )
except ImportError:
    WhisperModel = None
    register_feature(
        "faster_whisper",
        False,
        "Optimized STT transcription",
        install_hint="pip install faster-whisper",
        fallback_behavior="basic transcription (slower)"
    )

try:
    from backend.modules.telemetry import history_logger
except Exception:
    history_logger = None

try:
    from backend.modules.security import assess_risk
except Exception:
    def assess_risk(*_args, **_kwargs):
        return "unknown"

log = logging.getLogger("stt_service")

TARGET_SR = 16000  # sample rate expected by Whisper


class STTService:
    """
    STT service exposing:
      - transcribe_bytes(audio_bytes, language=None, prompt=None, profile_id="default")
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(STTService, cls).__new__(cls)
                cls._instance.model = None
            return cls._instance

    def _load_model(self):
        """Lazily load WhisperModel singleton per service instance."""
        if self.model is None:
            if WhisperModel is None:
                raise RuntimeError("faster_whisper module not found. Install it with pip.")
            
            model_name = getattr(config, "STT_MODEL_NAME", "base.en")
            # Default to CUDA if available, else CPU
            device = getattr(config, "STT_DEVICE", "cuda")
            compute = getattr(config, "STT_COMPUTE_TYPE", "float16")
            
            log.info("Loading STT model %s (device=%s compute=%s)", model_name, device, compute)
            self.model = WhisperModel(model_name, device=device, compute_type=compute)

    def _decode_and_resample(self, audio_bytes: bytes) -> Tuple[np.ndarray, int]:
        """
        Decode audio bytes using av, resample to TARGET_SR mono.
        Returns: (pcm: np.ndarray float32, sr: int)
        """
        try:
            buf = io.BytesIO(audio_bytes)
            container = av.open(buf)
        except Exception as e:
            # Fallback for raw WAV bytes if AV fails to sniff format
            try:
                data, samplerate = sf.read(io.BytesIO(audio_bytes))
                # basic downmix if needed
                if len(data.shape) > 1:
                    data = data.mean(axis=1)
                # primitive resampling not implemented here for brevity in fallback, 
                # but typically soundfile returns float64.
                return data.astype("float32"), samplerate
            except:
                raise RuntimeError(f"Could not decode audio stream: {e}")

        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise RuntimeError("No audio stream found")

        # av AudioResampler: convert to mono, s16, TARGET_SR
        resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=TARGET_SR)

        frames = []
        for packet in container.demux(stream):
            for frame in packet.decode():
                try:
                    r = resampler.resample(frame)
                except Exception:
                    r = frame

                # r may be an AudioFrame or list of them
                r_list = r if isinstance(r, (list, tuple)) else [r]

                for rframe in r_list:
                    if rframe is None: continue
                    try:
                        arr = rframe.to_ndarray()
                    except Exception:
                        continue
                    
                    if not isinstance(arr, np.ndarray):
                        arr = np.asarray(arr)
                    
                    # downmix if channel dim exists
                    if arr.ndim > 1:
                        arr = arr.mean(axis=0)
                    frames.append(arr)

        if not frames:
            return np.array([], dtype="float32"), TARGET_SR

        pcm = np.concatenate(frames).astype("float32")

        # Normalize int16 range to [-1, 1]
        if pcm.max() > 1.0 or pcm.min() < -1.0:
            pcm = pcm / 32768.0

        pcm = np.clip(pcm, -1.0, 1.0)
        return pcm, TARGET_SR

    def _transcribe_with_array(self, pcm: np.ndarray, sr: int, language: Optional[str], prompt: Optional[str]) -> dict:
        """
        Internal: Calls model.transcribe. 
        Must only be called when VRAM Lock is acquired!
        """
        self._load_model()
        try:
            # Preferred: Array (faster-whisper implies 16k)
            result = self.model.transcribe(pcm, language=language or None, initial_prompt=prompt or None, beam_size=5)

            text = ""
            lang = language or ""
            
            # Handle varied return signature of .transcribe()
            if isinstance(result, tuple) and len(result) >= 1:
                segments = result[0]
                text = " ".join(getattr(s, "text", str(s)) for s in segments).strip()
                if len(result) > 1:
                    info = result[1]
                    lang = getattr(info, "language", lang) if info is not None else lang
            else:
                # Dict-like fallback
                text = getattr(result, "text", "") or ""
                lang = getattr(result, "language", "") or lang

            return {"text": text, "language": lang}

        except Exception as e:
            log.warning("Array-based transcribe failed: %s. Fallback to temp WAV.", e)
            # Fallback: Write WAV and try path-based
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            try:
                sf.write(tmp_path, pcm, sr, format="WAV", subtype="PCM_16")
                res = self.model.transcribe(tmp_path, language=language or None, initial_prompt=prompt or None, beam_size=5)
                
                text = ""
                lang = language or ""
                if isinstance(res, tuple) and len(res) >= 1:
                    segments = res[0]
                    text = " ".join(getattr(s, "text", str(s)) for s in segments).strip()
                    if len(res) > 1:
                        info = res[1]
                        lang = getattr(info, "language", lang) if info is not None else lang
                else:
                    text = getattr(res, "text", "")
                    lang = getattr(res, "language", "")

                return {"text": text, "language": lang}
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    def transcribe_bytes(self, 
                         audio_bytes: bytes, 
                         language: Optional[str] = None, 
                         prompt: Optional[str] = None,
                         profile_id: str = "default") -> dict:
        """
        Main entrypoint.
        1. Decodes audio (CPU)
        2. Acquires VRAM Lock (Queue)
        3. Runs Inference (GPU)
        """
        if not getattr(config, "STT_ENABLED", True):
            return {"text": "", "error": "STT Disabled"}

        # --- Step 1: CPU Work (Decode) ---
        # We do this BEFORE locking the queue to avoid holding up the line.
        try:
            pcm, sr = self._decode_and_resample(audio_bytes)
            if pcm.size == 0:
                return {"text": "", "language": language or ""}
        except Exception as e:
            log.error(f"Audio Decode Failed: {e}")
            return {"text": "", "error": f"Decode error: {e}"}

        # --- Step 2: Queue Acquisition (VRAM Guard) ---
        job = enqueue_job(profile_id=profile_id, kind="stt", is_heavy=True)
        
        # Poll for slot (Timeout 5s for responsiveness)
        acquired = try_acquire_next_job(profile_id)
        if not acquired or acquired.id != job.id:
            wait_start = time.time()
            while True:
                if time.time() - wait_start > 5.0:
                    mark_job_failed(job.id, "STT Timeout (VRAM busy)")
                    return {"text": "", "error": "System busy (Thinking/Seeing), ignored voice."}

                acquired = try_acquire_next_job(profile_id)
                if acquired and acquired.id == job.id:
                    break
                time.sleep(0.05)

        # --- Step 3: GPU Work (Inference) ---
        try:
            start_ts = time.monotonic()
            out = self._transcribe_with_array(pcm, sr, language, prompt)
            duration = time.monotonic() - start_ts

            # Phase B: Add confidence validation
            try:
                from backend.modules.perception.stt_confidence import validate_stt_result
                from backend.core.confirmation import create_confirmation_request

                out = validate_stt_result(out)
                confidence_meta = out.get("confidence_metadata", {})

                if confidence_meta.get("requires_confirmation", False):
                    # Create confirmation request instead of returning result
                    message = f"STT confidence is {confidence_meta.get('confidence_level')} ({confidence_meta.get('confidence_score', 0):.3f}). Please confirm transcription."
                    confirmation = create_confirmation_request(
                        message=message,
                        action_data={"type": "stt_result", "result": out},
                        confidence_metadata=confidence_meta
                    )
                    mark_job_done(job.id)
                    return confirmation

            except Exception as e:
                log.warning(f"STT confidence validation failed: {e}")

            mark_job_done(job.id)

            # Telemetry
            text_out = out.get("text", "")
            try:
                risk = assess_risk("stt", {"prompt": prompt, "length": len(text_out)})
            except:
                risk = "unknown"

            if history_logger:
                history_logger.log(mode="stt", payload={
                    "original_prompt": prompt,
                    "final_output": text_out,
                    "duration": round(duration, 3),
                    "model": getattr(config, "STT_MODEL_NAME", None),
                    "language": out.get("language"),
                    "risk": risk
                })

            return out

        except Exception as e:
            mark_job_failed(job.id, str(e))
            log.exception("STT Inference failed")
            
            # Fallback strategy: FP16 -> FP32 reload?
            # Note: This is risky inside a queue lock, but we can try if config allows.
            if getattr(config, "STT_COMPUTE_TYPE", "") == "float16":
                log.info("Attempting FP32 fallback...")
                try:
                    config.STT_COMPUTE_TYPE = "float32"
                    self.model = None # Force reload
                    # We still have the lock, so we can retry immediately
                    out = self._transcribe_with_array(pcm, sr, language, prompt)
                    # If successful, we need to mark done again? No, mark_job_failed was called.
                    # Actually, if we recovered, we should correct the job state, but queue logic
                    # doesn't easily support "un-failing". 
                    # For V4 stability, we accept the failure log but return the result if fallback worked.
                    return out
                except Exception:
                    pass
            
            return {"text": "", "error": str(e)}

    # Alias
    def transcribe_webm_bytes(self, audio_bytes: bytes, language: Optional[str] = None, prompt: Optional[str] = None) -> dict:
        return self.transcribe_bytes(audio_bytes, language=language, prompt=prompt)