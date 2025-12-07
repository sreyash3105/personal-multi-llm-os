import base64
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel

from config import CHAT_MODEL_NAME, AVAILABLE_MODELS, VISION_ENABLED, SMART_CHAT_MODEL_NAME
from vision_pipeline import run_vision

from pipeline import call_ollama
from history import history_logger
from chat_storage import (
    list_profiles,
    create_profile,
    rename_profile,
    delete_profile,
    set_profile_model,
    list_chats,
    create_chat,
    rename_chat,
    delete_chat,
    set_chat_model,
    get_messages,
    append_message,
    get_profile,
    get_chat,
)

router = APIRouter()


# =========================
# Pydantic models
# =========================

class ProfileCreate(BaseModel):
    display_name: Optional[str] = None
    model_override: Optional[str] = None


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    model_override: Optional[str] = None


class ChatCreate(BaseModel):
    profile_id: str
    display_name: Optional[str] = None
    model_override: Optional[str] = None


class ChatUpdate(BaseModel):
    display_name: Optional[str] = None
    model_override: Optional[str] = None


class ChatRequest(BaseModel):
    prompt: str
    profile_id: Optional[str] = None
    chat_id: Optional[str] = None
    smart: Optional[bool] = False  # when True, use SMART_CHAT_MODEL_NAME


class ChatResponse(BaseModel):
    output: str
    profile_id: str
    chat_id: str


class ProfileSummaryRequest(BaseModel):
    profile_id: str


# =========================
# Helpers
# =========================

def _ensure_profile(profile_id: Optional[str]) -> Dict[str, Any]:
    profiles = list_profiles()

    if not profile_id:
        if profiles:
            return profiles[0]
        return create_profile(display_name=None, model_override=None)

    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")
    return prof


def _ensure_chat(profile_id: str, chat_id: Optional[str]) -> Dict[str, Any]:
    chats = list_chats(profile_id)

    if not chat_id:
        if chats:
            return chats[0]
        return create_chat(profile_id=profile_id)

    chat = get_chat(profile_id, chat_id)
    if not chat:
        return create_chat(profile_id=profile_id, display_name=chat_id)

    return {
        "id": chat.get("id", chat_id),
        "display_name": chat.get("display_name", chat_id),
        "model_override": chat.get("model_override"),
        "created_at": chat.get("created_at", ""),
        "message_count": len(chat.get("messages") or []),
    }


def _resolve_model(profile: Dict[str, Any], chat: Dict[str, Any]) -> str:
    chat_model = chat.get("model_override")
    if chat_model:
        return chat_model

    prof_model = profile.get("model_override")
    if prof_model:
        return prof_model

    return CHAT_MODEL_NAME


# =========================
# Profile management API
# =========================

@router.get("/api/chat/profiles")
def api_list_profiles():
    return {"profiles": list_profiles()}


@router.post("/api/chat/profiles")
def api_create_profile(body: ProfileCreate):
    prof = create_profile(
        display_name=body.display_name,
        model_override=body.model_override,
    )
    return prof


@router.patch("/api/chat/profiles/{profile_id}")
def api_update_profile(profile_id: str, body: ProfileUpdate):
    if body.display_name is not None:
        rename_profile(profile_id, body.display_name)
    if body.model_override is not None:
        set_profile_model(profile_id, body.model_override)
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return prof


@router.delete("/api/chat/profiles/{profile_id}")
def api_delete_profile(profile_id: str):
    ok = delete_profile(profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profile not found or could not be deleted")
    return {"ok": True}


# =========================
# Chat management API
# =========================

@router.get("/api/chat/chats")
def api_list_chats(profile_id: str = Query(...)):
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"profile": prof, "chats": list_chats(profile_id)}


@router.post("/api/chat/chats")
def api_create_chat_endpoint(body: ChatCreate):
    prof = get_profile(body.profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    chat = create_chat(
        profile_id=body.profile_id,
        display_name=body.display_name,
        model_override=body.model_override,
    )
    return chat


@router.patch("/api/chat/chats/{profile_id}/{chat_id}")
def api_update_chat(profile_id: str, chat_id: str, body: ChatUpdate):
    if body.display_name is not None:
        rename_chat(profile_id, chat_id, body.display_name)
    if body.model_override is not None:
        set_chat_model(profile_id, chat_id, body.model_override)

    chat = get_chat(profile_id, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@router.delete("/api/chat/chats/{profile_id}/{chat_id}")
def api_delete_chat_endpoint(profile_id: str, chat_id: str):
    ok = delete_chat(profile_id, chat_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat not found or could not be deleted")
    return {"ok": True}


# =========================
# Messages API
# =========================

@router.get("/api/chat/messages")
def api_get_messages(profile_id: str = Query(...), chat_id: str = Query(...)):
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    chat = get_chat(profile_id, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages = get_messages(profile_id, chat_id)
    return {
        "profile_id": profile_id,
        "chat_id": chat_id,
        "messages": messages,
    }


# =========================
# Vision-in-chat API (one-shot)
# =========================

@router.post("/api/chat/vision")
async def api_chat_vision(
    profile_id: str = Form(...),
    chat_id: str = Form(...),
    prompt: str = Form(""),
    mode: str = Form("auto"),
    file: UploadFile = File(...),
):
    """
    Run a one-off vision analysis inside a chat.

    - Uses vision model (llava) via run_vision.
    - Stores the image as a base64 data URL embedded in the message text.
    - Renders as a thumbnail in the chat bubble.
    """
    if not VISION_ENABLED:
        raise HTTPException(status_code=400, detail="Vision is disabled in config.")

    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    chat = get_chat(profile_id, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="No image data received")

    # Vision analysis
    vision_output = run_vision(
        image_bytes=image_bytes,
        user_prompt=prompt or "",
        mode=mode or "auto",
    )

    # Encode image as base64 data URL (saved in chat)
    mime = file.content_type or "image/png"
    if not mime.startswith("image/"):
        mime = "image/png"
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    user_msg_text = prompt.strip() if prompt else "(no prompt)"
    # Special encoding: __IMG__<mime>|<b64>\n<caption>
    payload_text = f"__IMG__{mime}|{b64}\n{user_msg_text}"

    append_message(profile_id, chat_id, "user", payload_text)
    append_message(profile_id, chat_id, "assistant", vision_output)

    history_logger.log(
        {
            "mode": f"chat_vision_{mode or 'auto'}",
            "original_prompt": prompt,
            "normalized_prompt": prompt,
            "coder_output": None,
            "reviewer_output": None,
            "final_output": vision_output,
            "escalated": False,
            "escalation_reason": "",
            "judge": None,
            "chat_profile_id": profile_id,
            "chat_profile_name": prof.get("display_name"),
            "chat_id": chat_id,
            "chat_model_used": "vision",
        }
    )

    return {
        "profile_id": profile_id,
        "chat_id": chat_id,
        "output": vision_output,
    }


# =========================
# Models API
# =========================

@router.get("/api/chat/models")
def api_list_models():
    models = sorted(set(AVAILABLE_MODELS.values()))
    return {
        "default_model": CHAT_MODEL_NAME,
        "smart_model": SMART_CHAT_MODEL_NAME,
        "available_models": models,
    }


# =========================
# Main chat endpoint
# =========================

@router.post("/api/chat", response_model=ChatResponse)
def api_chat(req: ChatRequest):
    profile = _ensure_profile(req.profile_id)
    profile_id = profile["id"]

    chat_meta = _ensure_chat(profile_id, req.chat_id)
    chat_id = chat_meta["id"]

    messages = get_messages(profile_id, chat_id)

    # base model from profile/chat
    model_name = _resolve_model(profile, chat_meta)

    # Smart override: force SMART_CHAT_MODEL_NAME if requested
    if req.smart:
        model_name = SMART_CHAT_MODEL_NAME

    from prompts import CHAT_SYSTEM_PROMPT

    convo_lines: List[str] = []
    for msg in messages:
        role = msg.get("role", "user").upper()
        text = msg.get("text", "")
        convo_lines.append(f"{role}: {text}")

    convo_lines.append(f"USER: {req.prompt}")
    convo_block = "\n".join(convo_lines)

    full_prompt = f"""{CHAT_SYSTEM_PROMPT}

Current profile: {profile.get("display_name") or profile_id}

Conversation so far:
{convo_block}

ASSISTANT:""".strip()

    answer = call_ollama(full_prompt, model_name)

    append_message(profile_id, chat_id, "user", req.prompt)
    append_message(profile_id, chat_id, "assistant", answer)

    history_logger.log(
        {
            "mode": "chat",
            "original_prompt": req.prompt,
            "normalized_prompt": req.prompt,
            "coder_output": None,
            "reviewer_output": None,
            "final_output": answer,
            "escalated": False,
            "escalation_reason": "",
            "judge": None,
            "chat_profile_id": profile_id,
            "chat_profile_name": profile.get("display_name"),
            "chat_id": chat_id,
            "chat_model_used": model_name,
        }
    )

    return ChatResponse(output=answer, profile_id=profile_id, chat_id=chat_id)


# =========================
# Profile summary API (optional, not used by current UI)
# =========================

@router.post("/api/chat/profile_summary")
def api_profile_summary(body: ProfileSummaryRequest):
    prof = get_profile(body.profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    chats = list_chats(body.profile_id)
    if not chats:
        return {
            "profile_id": body.profile_id,
            "summary": "(No chats to summarize yet for this profile.)",
        }

    lines: List[str] = []
    for chat_meta in chats:
        cid = chat_meta.get("id")
        cname = chat_meta.get("display_name") or cid
        lines.append(f"[CHAT {cid} - {cname}]")
        msgs = get_messages(body.profile_id, cid) or []
        recent_msgs = msgs[-80:]
        for m in recent_msgs:
            ts = m.get("ts", "")
            role = (m.get("role") or "user").upper()
            text = m.get("text") or ""
            lines.append(f"{ts} {role}: {text}")
        lines.append("")

    raw_block = "\n".join(lines)

    summary_system_prompt = """
You are an assistant summarizing a developer's multi-chat workspace for a single project/profile.

You will receive multiple chats in this format:

[CHAT a - API Planning]
<timestamp> USER: ...
<timestamp> ASSISTANT: ...
...

Your job:
1) For EACH chat, write 2–6 bullet points summarizing what was discussed, decided, or planned.
2) Then write a final section called "Overall Profile Summary" that:
   - connects the dots between the chats,
   - highlights main decisions,
   - calls out open questions / TODOs,
   - and describes the current state of the project.
3) Focus on technical and planning content, not small talk.
4) Output plain text (no markdown fences). Bullet points are fine.
""".strip()

    prompt = f"""{summary_system_prompt}

Profile name: {prof.get("display_name") or body.profile_id}

Raw chat logs:
{raw_block}
""".strip()

    model_name = prof.get("model_override") or CHAT_MODEL_NAME
    summary_text = call_ollama(prompt, model_name)

    history_logger.log(
        {
            "mode": "chat_profile_summary",
            "original_prompt": f"[PROFILE_SUMMARY] {body.profile_id}",
            "normalized_prompt": f"Summarize profile {body.profile_id}",
            "coder_output": None,
            "reviewer_output": None,
            "final_output": summary_text,
            "escalated": False,
            "escalation_reason": "",
            "judge": None,
            "chat_profile_id": body.profile_id,
            "chat_profile_name": prof.get("display_name"),
            "chat_id": None,
            "chat_model_used": model_name,
        }
    )

    return {
        "profile_id": body.profile_id,
        "summary": summary_text,
    }
