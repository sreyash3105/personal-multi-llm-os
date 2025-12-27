from __future__ import annotations

from typing import Optional

try:
    from backend.modules.tts.tts_service import tts_service as _service
except ImportError:
    _service = None


def synthesize(text: str, voice: Optional[str] = None) -> dict:
    if _service is None:
        raise ValueError("TTS service is unavailable.")

    result = _service.synthesize(text, voice)

    return {
        "ok": True,
        "audio_b64": result.get("audio_b64"),
        "duration_s": result.get("duration_s"),
        "voice": result.get("voice"),
        "text_length": result.get("text_length"),
    }
