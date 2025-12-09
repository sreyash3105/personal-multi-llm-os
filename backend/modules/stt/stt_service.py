from faster_whisper import WhisperModel
import io
import av
import soundfile as sf
from backend.core import config


class STTService:
    """
    Local GPU speech-to-text using Whisper-small.
    Accepts WebM/Opus bytes from the browser → decodes → transcribes.
    """

    def __init__(self):
        self.model = None

    def _load_model(self):
        if self.model is None:
            self.model = WhisperModel(
                config.STT_MODEL_NAME,
                device=config.STT_DEVICE,
                compute_type=config.STT_COMPUTE_TYPE,
            )

    def transcribe_webm_bytes(self, audio_bytes: bytes, language="en"):
        if not config.STT_ENABLED:
            raise RuntimeError("STT disabled")

        self._load_model()

                # Decode WebM/Opus → PCM float32 mono audio
        container = av.open(io.BytesIO(audio_bytes))
        stream = next(s for s in container.streams if s.type == "audio")

        audio = []
        for frame in container.decode(stream):
            arr = frame.to_ndarray()  # (channels, samples) or (samples,)
            # Downmix multi-channel → mono
            if arr.ndim == 2:
                arr = arr.mean(axis=0)
            arr = arr.astype("float32")
            # Normalize if it's in int16 range
            if arr.max() > 1.0 or arr.min() < -1.0:
                arr = arr / 32768.0
            audio.append(arr)

        if not audio:
            return ""

        import numpy as np
        pcm = np.concatenate(audio).astype("float32")
        segments, _ = self.model.transcribe(pcm, language=language)

        return " ".join(seg.text for seg in segments).strip()
