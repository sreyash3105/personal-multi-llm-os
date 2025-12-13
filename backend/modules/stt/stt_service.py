# backend/modules/stt/stt_service.py
"""
Robust STT service wrapper for faster-whisper.

Features:
 - decode many container formats via av
 - resample to TARGET_SR (16000) mono using av.AudioResampler
 - normalize to float32 in [-1, 1]
 - call faster-whisper model.transcribe with numpy (assumes 16k) or fallback to temp WAV path
 - fp16 -> float32 model reload fallback
 - telemetry hooks (history_logger, assess_risk) attempted if available
"""

import io
import os
import tempfile
import logging
from typing import Optional

import av
import numpy as np
import soundfile as sf

from faster_whisper import WhisperModel

from backend.core import config  # your project config

# Try to import telemetry hooks without failing if absent
try:
    from backend.modules.telemetry import history_logger
except Exception:
    history_logger = None

try:
    from backend.modules.security import assess_risk
except Exception:
    # fallback that returns "unknown" risk
    def assess_risk(*_args, **_kwargs):
        return "unknown"

log = logging.getLogger("stt_service")

TARGET_SR = 16000  # sample rate expected by Whisper


class STTService:
    """
    STT service exposing:
      - transcribe_bytes(audio_bytes, language=None, prompt=None)
      - transcribe_webm_bytes(...)  (alias for compatibility)
    """

    def __init__(self):
        self.model = None

    def _load_model(self):
        """Lazily load WhisperModel singleton per service instance."""
        if self.model is None:
            model_name = getattr(config, "STT_MODEL_NAME", "small")
            device = getattr(config, "STT_DEVICE", "cuda")
            compute = getattr(config, "STT_COMPUTE_TYPE", "float16")
            log.info("Loading STT model %s (device=%s compute=%s)", model_name, device, compute)
            # Initialize model; exceptions propagate to caller
            self.model = WhisperModel(model_name, device=device, compute_type=compute)

    def _decode_and_resample(self, audio_bytes: bytes):
        """
        Decode audio bytes using av, resample to TARGET_SR mono.
        Returns: (pcm: np.ndarray float32, sr: int)
        Handles cases where resampler.resample(...) returns a single frame or a list of frames.
        """
        buf = io.BytesIO(audio_bytes)
        container = av.open(buf)
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
                    # If resampling fails for this frame, fall back to using original frame
                    r = frame

                # r may be an AudioFrame or a list/tuple of AudioFrames
                r_list = r if isinstance(r, (list, tuple)) else [r]

                for rframe in r_list:
                    if rframe is None:
                        continue
                    try:
                        arr = rframe.to_ndarray()
                    except Exception:
                        # skip frames that cannot be converted
                        continue
                    # ensure numpy array
                    if not isinstance(arr, np.ndarray):
                        arr = np.asarray(arr)
                    # arr may be (channels, samples) or (samples,)
                    if arr.ndim > 1:
                        # downmix to mono by averaging channels
                        arr = arr.mean(axis=0)
                    frames.append(arr)

        if not frames:
            # no audio decoded
            return np.array([], dtype="float32"), TARGET_SR

        pcm = np.concatenate(frames).astype("float32")

        # Normalize: many containers produce int16 ranges; convert to [-1,1]
        if pcm.max() > 1.0 or pcm.min() < -1.0:
            # assume int16 range
            pcm = pcm / 32768.0

        pcm = np.clip(pcm, -1.0, 1.0)
        return pcm, TARGET_SR

    def _transcribe_with_array(self, pcm: "np.ndarray", sr: int, language: Optional[str], prompt: Optional[str]) -> dict:
        """
        Try to call model.transcribe with numpy array.
        (Removed sample_rate arg as faster-whisper infers 16k for arrays).
        If that fails, write a temporary WAV file and call model.transcribe(path).
        Returns: {"text": str, "language": str}
        """
        self._load_model()
        try:
            # Preferred path: array (faster-whisper assumes 16k)
            # FIX: Removed 'sample_rate=sr' which caused TypeError
            result = self.model.transcribe(pcm, language=language or None, initial_prompt=prompt or None)

            # result shapes vary by faster-whisper version:
            # - sometimes (segments, info)
            # - sometimes object/dict with .text / .language
            text = ""
            lang = language or ""
            if isinstance(result, tuple) and len(result) >= 1:
                segments = result[0]
                # join texts from segments
                text = " ".join(getattr(s, "text", str(s)) for s in segments).strip()
                if len(result) > 1:
                    info = result[1]
                    lang = getattr(info, "language", lang) if info is not None else lang
            else:
                # object/dict variant
                text = getattr(result, "text", "") or (result.get("text") if isinstance(result, dict) else "")
                lang = getattr(result, "language", "") or (result.get("language") if isinstance(result, dict) else language or "")

            return {"text": text, "language": lang}
        except Exception as e:
            log.warning("Array-based transcribe failed (%s): %s. Falling back to temp WAV path.", type(e).__name__, e)
            # fallback: write WAV and call path-based API
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            try:
                sf.write(tmp_path, pcm, sr, format="WAV", subtype="PCM_16")
                res = self.model.transcribe(tmp_path, language=language or None, initial_prompt=prompt or None)
                text = ""
                lang = language or ""
                if isinstance(res, tuple) and len(res) >= 1:
                    segments = res[0]
                    text = " ".join(getattr(s, "text", str(s)) for s in segments).strip()
                    if len(res) > 1:
                        info = res[1]
                        lang = getattr(info, "language", lang) if info is not None else lang
                else:
                    text = getattr(res, "text", "") or (res.get("text") if isinstance(res, dict) else "")
                    lang = getattr(res, "language", "") or (res.get("language") if isinstance(res, dict) else language or "")
                return {"text": text, "language": lang}
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def transcribe_bytes(self, audio_bytes: bytes, language: Optional[str] = None, prompt: Optional[str] = None) -> dict:
        """
        Main entrypoint for HTTP router to call.
        Returns dict {"text": ..., "language": ...}
        """
        if not getattr(config, "STT_ENABLED", True):
            raise RuntimeError("STT disabled in config")

        try:
            pcm, sr = self._decode_and_resample(audio_bytes)
            if pcm.size == 0:
                return {"text": "", "language": language or ""}

            out = self._transcribe_with_array(pcm, sr, language, prompt)

            # telemetry - best-effort
            try:
                risk = assess_risk("stt", {"prompt": prompt, "length": len(out.get("text", ""))})
            except Exception:
                risk = "unknown"
            if history_logger is not None:
                try:
                    history_logger.log(mode="stt", payload={
                        "original_prompt": prompt,
                        "final_output": out.get("text"),
                        "model": getattr(config, "STT_MODEL_NAME", None),
                        "language": out.get("language"),
                        "risk": risk,
                    })
                except Exception:
                    log.debug("history_logger.log failed")

            return out

        except Exception as e:
            log.exception("STT processing failed")
            # log telemetry error
            if history_logger is not None:
                try:
                    history_logger.log(mode="stt_error", payload={"error": str(e)})
                except Exception:
                    pass

            # FP16 -> FP32 fallback strategy
            if getattr(config, "STT_COMPUTE_TYPE", "") == "float16":
                log.info("Attempting fallback: reload model with compute_type=float32")
                try:
                    # mutate config for fallback and reload model
                    config.STT_COMPUTE_TYPE = "float32"
                    self.model = None
                    self._load_model()
                    pcm, sr = self._decode_and_resample(audio_bytes)
                    return self._transcribe_with_array(pcm, sr, language, prompt)
                except Exception:
                    log.exception("Fallback also failed")
            # re-raise so router can return 500
            raise

    # Backwards-compatible alias (some routers call transcribe_webm_bytes)
    def transcribe_webm_bytes(self, audio_bytes: bytes, language: Optional[str] = None, prompt: Optional[str] = None) -> dict:
        return self.transcribe_bytes(audio_bytes, language=language, prompt=prompt)