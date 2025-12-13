from __future__ import annotations
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# --- Pipelines ---
from backend.modules.chat.chat_pipeline import run_chat_smart
from backend.modules.chat.chat_ui import handle_chat_turn
from backend.modules.code.pipeline import run_coder, run_reviewer, run_smart_code_pipeline
from backend.modules.vision.vision_pipeline import run_vision
from backend.modules.automation.executor import plan_and_execute
from backend.modules.tts.tts_router import router as tts_router

# --- Telemetry & Config ---
from backend.modules.telemetry.history import history_logger
from backend.core.config import TOOLS_IN_CHAT_ENABLED

router = APIRouter()
router.include_router(tts_router, prefix="/api/tts", tags=["tts"])

# --- Data Models ---

class ChatRequest(BaseModel):
    profile_id: str
    user_prompt: str
    chat_id: str
    smart_mode: bool = False

class CodeRequest(BaseModel):
    prompt: str
    profile_id: Optional[str] = None
    smart_mode: bool = True  # Defaults to the new Smart Pipeline

class AutomationRequest(BaseModel):
    prompt: str
    profile_id: Optional[str] = None
    execute: bool = False

class VisionRequest(BaseModel):
    image_base64: str
    prompt: str = ""
    mode: str = "auto"

# --- Endpoints ---

@router.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Unified chat endpoint.
    - Normal Mode: fast, standard chat.
    - Smart Mode: Planner -> Answer -> Judge (with full trace logging).
    """
    # 1. Load context/profile logic is handled inside chat_ui.handle_chat_turn
    #    For Smart Mode, we bypass the standard UI handler partially to use the pipeline directly,
    #    OR we can pass a flag to handle_chat_turn. 
    #    To keep it clean, we'll route explicitly here.
    
    if req.smart_mode:
        # Load recent messages (simplified for this endpoint, usually handled by UI state)
        # For a stateless API call, we might assume just the prompt, 
        # but ideal usage is via the UI which manages state.
        # We will trigger the Smart Pipeline via the UI handler which supports it.
        return handle_chat_turn(
            profile_id=req.profile_id,
            chat_id=req.chat_id,
            user_input=req.user_prompt,
            mode_override="smart" 
        )
    else:
        return handle_chat_turn(
            profile_id=req.profile_id,
            chat_id=req.chat_id,
            user_input=req.user_prompt,
            mode_override="normal"
        )

@router.post("/api/code/generate")
async def generate_code_endpoint(req: CodeRequest):
    """
    Generates code.
    If smart_mode=True, runs Coder -> Reviewer -> Judge -> Risk -> History.
    """
    try:
        if req.smart_mode:
            # 🟢 The New Black Box Pipeline
            result = run_smart_code_pipeline(req.prompt, req.profile_id)
            return {
                "ok": True, 
                "code": result["final_code"], 
                "trace": result  # Contains planner, judge, risk scores
            }
        else:
            # Legacy/Fast mode (Coder only)
            code = run_coder(req.prompt, req.profile_id)
            return {"ok": True, "code": code}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/api/automation/run")
async def automation_endpoint(req: AutomationRequest):
    """
    Runs PC Automation.
    Logs full Plan -> Execute -> Risk trace to history.
    """
    try:
        # The executor handles its own history logging
        result = plan_and_execute(req.prompt, context={"profile_id": req.profile_id}, execute=req.execute)
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/api/vision/analyze")
async def vision_endpoint(req: VisionRequest):
    """
    Analyzes images (Describe, OCR, Code, etc).
    """
    try:
        import base64
        image_bytes = base64.b64decode(req.image_base64)
        result = run_vision(image_bytes, req.user_prompt, mode=req.mode)
        return {"ok": True, "text": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}