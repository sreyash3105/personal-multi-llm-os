"""
tts_router.py

FastAPI router for Text-to-Speech (TTS).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# guarded import of the service
try:
    from backend.modules.tts.tts_service import tts_service as _service
except ImportError:
    # Fallback for systems where tts_service is not fully implemented
    _service = None

router = APIRouter()

class TTSSynthRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    profile_id: Optional[str] = None
    chat_id: Optional[str] = None

@router.post("/api/tts/synthesize")
async def synthesize_endpoint(req: TTSSynthRequest):
    """
    Synthesizes the provided text into audio (base64 encoded).
    """
    if _service is None:
        raise HTTPException(status_code=503, detail="TTS service is unavailable.")

    try:
        # We assume the text from the final output is safe/clamped by the chat pipeline
        result = _service.synthesize(req.text, req.voice)
        
        return {
            "ok": True,
            "audio_b64": result.get("audio_b64"),
            "duration_s": result.get("duration_s"),
            "voice": result.get("voice"),
            "text_length": result.get("text_length"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {str(e)}")