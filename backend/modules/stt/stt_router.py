# backend/modules/stt/stt_router.py
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import logging

from backend.core import config
from backend.modules.stt.stt_service import STTService

# adjust telemetry import if necessary
try:
    from backend.core.telemetry import history_logger
except Exception:
    history_logger = None

log = logging.getLogger("stt_router")
router = APIRouter()
_service = STTService()

@router.get("/health")
async def stt_health():
    """
    Simple health check — ensures model loads.
    """
    if not getattr(config, "STT_ENABLED", True):
        return JSONResponse({"status": "disabled"})
    try:
        _service._load_model()
        return JSONResponse({"status": "ok", "model": getattr(config, "STT_MODEL_NAME", None)})
    except Exception as e:
        log.exception("STT health check failed")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)

@router.post("/transcribe")
async def transcribe_endpoint(
    file: UploadFile = File(...),
    language: str = Form(None),
    prompt: str = Form(None),
):
    if not getattr(config, "STT_ENABLED", True):
        raise HTTPException(status_code=503, detail="STT disabled in config")
    try:
        audio_bytes = await file.read()
        result = _service.transcribe_bytes(audio_bytes, language=language, prompt=prompt)
        return JSONResponse(result)
    except Exception as e:
        log.exception("STT API error")
        if history_logger is not None:
            try:
                history_logger.log(mode="stt_error", payload={"error": str(e)})
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="STT failed: " + str(e))
