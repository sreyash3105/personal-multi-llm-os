from __future__ import annotations

from typing import Optional

from backend.modules.stt.stt_service import STTService

try:
    from backend.core.telemetry import history_logger
except Exception:
    history_logger = None

_service = STTService()


def stt_health() -> dict:
    from backend.core import config
    if not getattr(config, "STT_ENABLED", True):
        return {"status": "disabled"}
    try:
        _service._load_model()
        return {"status": "ok", "model": getattr(config, "STT_MODEL_NAME", None)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def transcribe(
    audio_bytes: bytes,
    language: Optional[str] = None,
    prompt: Optional[str] = None
) -> dict:
    from backend.core import config
    if not getattr(config, "STT_ENABLED", True):
        raise ValueError("STT disabled in config")
    result = _service.transcribe_bytes(audio_bytes, language=language, prompt=prompt)
    if history_logger is not None:
        try:
            history_logger.log(mode="stt", payload={"language": language, "prompt": prompt})
        except Exception:
            pass
    return result
