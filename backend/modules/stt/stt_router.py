from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.modules.stt.stt_service import STTService
from backend.core import config

stt_router = APIRouter(prefix="/api/stt", tags=["stt"])
service = STTService()

@stt_router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not config.STT_ENABLED:
        raise HTTPException(status_code=503, detail="STT disabled")

    try:
        audio_bytes = await file.read()
        text = service.transcribe_webm_bytes(audio_bytes)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
