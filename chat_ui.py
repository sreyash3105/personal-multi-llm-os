"""
Chat UI + API layer for multi-profile chat workspace.

Responsibilities:
- Multi-profile, multi-chat text workspace
- Main /api/chat endpoint (normal + smart chat)
- Vision-in-chat endpoint
- Tools-in-chat integration (///tool, ///tool+chat)
- Simple profile/chat/messages CRUD for static/chat.html
- Profile KB preview + note creation / deletion

This module is "sacred" in V3.4.x — only incremental, low-risk edits allowed.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from pydantic import BaseModel

from config import (
    CHAT_MODEL_NAME,
    SMART_CHAT_MODEL_NAME,
    AVAILABLE_MODELS,
    VISION_ENABLED,
    TOOLS_IN_CHAT_ENABLED,
    TOOLS_CHAT_HYBRID_ENABLED,
    VISION_MODEL_NAME,
)
from history import history_logger
from pipeline import call_ollama
from profile_kb import (
    build_profile_context,
    build_profile_preview,
    add_snippet,
    delete_snippet,
    get_snippet,
)
from tools_runtime import execute_tool
from chat_pipeline import run_chat_smart
from vision_pipeline import run_vision
from chat_storage import (
    list_profiles,
    create_profile,
    rename_profile,
    set_profile_model,
    delete_profile,
    get_profile,
    list_chats,
    create_chat,
    rename_chat,
    set_chat_model,
    delete_chat,
    get_chat,
    get_messages,
    append_message,
)
from io_guards import sanitize_chat_input, clamp_chat_output, clamp_tool_output

router = APIRouter()


# =========================
# Pydantic models
# =========================


class ChatRequest(BaseModel):
    profile_id: Optional[str] = None
    chat_id: Optional[str] = None
    prompt: str
    smart: bool = False


class ChatResponse(BaseModel):
    output: str
    profile_id: str
    chat_id: str


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


class ProfileSummaryRequest(BaseModel):
    profile_id: str


class KbNoteCreate(BaseModel):
    profile_id: str
    title: str
    content: str


# =========================
# Internal helpers
# =========================


def _ensure_profile(profile_id: Optional[str]) -> Dict[str, Any]:
    """
    Ensure a valid profile exists.

    - If profile_id is provided and exists, return it.
    - If profile_id is missing or invalid, auto-create a "Default" profile.
    """
    if profile_id:
        prof = get_profile(profile_id)
        if prof:
            return prof

    profiles = list_profiles()
    if profiles:
        return profiles[0]

    prof = create_profile(display_name="Default", model_override=None)
    return prof


def _ensure_chat(profile_id: str, chat_id: Optional[str]) -> Dict[str, Any]:
    """
    Ensure a valid chat exists for a profile.

    - If chat_id is provided and exists, return it.
    - Else, create a new chat with a simple default name.
    """
    chats = list_chats(profile_id)
    if chat_id:
        for c in chats:
            if c.get("id") == chat_id:
                return c

    base_name = "Chat"
    existing_names = [c.get("display_name") or "" for c in chats]
    n = 1
    while True:
        candidate = f"{base_name} {n}"
        if candidate not in existing_names:
            break
        n += 1

    return create_chat(profile_id=profile_id, display_name=candidate, model_override=None)


def _resolve_model(profile: Dict[str, Any], chat_meta: Dict[str, Any]) -> str:
    """
    Decide which model to use based on chat + profile + config.
    Precedence:
      1) chat.model_override
      2) profile.model_override
      3) CHAT_MODEL_NAME
    """
    chat_override = (chat_meta.get("model_override") or "").strip()
    if chat_override:
        return chat_override

    profile_override = (profile.get("model_override") or "").strip()
    if profile_override:
        return profile_override

    return CHAT_MODEL_NAME


def _render_message_for_prompt(msg: Dict[str, Any]) -> str:
    """
    Render stored messages into a simple text conversation block for prompts.
    """
    role = (msg.get("role") or "user").strip().lower()
    text = msg.get("text") or ""

    if text.startswith("__IMG__"):
        parts = text.split("\n", 1)
        rest = parts[1] if len(parts) > 1 else ""
        return f"{role.upper()}: [IMAGE]\n{rest.strip()}"

    return f"{role.upper()}: {text}"


def _maybe_handle_tool_command(
    prompt_text: str,
    req: ChatRequest,
    profile: Dict[str, Any],
    profile_id: str,
    chat_meta: Dict[str, Any],
    chat_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Inspect prompt for ///tool / ///tool+chat commands and handle them.
    """
    text = (prompt_text or "").strip()

    if not text.startswith("///"):
        return None

    if not TOOLS_IN_CHAT_ENABLED:
        return {
            "output": "Tools-in-chat are currently disabled.",
            "profile_id": profile_id,
            "chat_id": chat_id,
        }

    is_hybrid = False
    cmd = None

    if text.startswith("///tool+chat"):
        is_hybrid = True
        cmd = "///tool+chat"
    elif text.startswith("///tool"):
        cmd = "///tool"

    if cmd is None:
        return None

    rest = text[len(cmd) :].strip()
    if not rest:
        return {
            "output": "Usage: ///tool TOOL_NAME {json_args} or ///tool+chat TOOL_NAME {json_args}",
            "profile_id": profile_id,
            "chat_id": chat_id,
        }

    parts = rest.split(None, 1)
    tool_name = parts[0]
    raw_args = parts[1] if len(parts) > 1 else "{}"

    try:
        args = json.loads(raw_args)
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be a JSON object.")
    except Exception as e:
        return {
            "output": f"Failed to parse tool arguments as JSON: {e}",
            "profile_id": profile_id,
            "chat_id": chat_id,
        }

    context = {
        "source": "chat",
        "profile_id": profile_id,
        "chat_id": chat_id,
    }

    record = execute_tool(tool_name, args, context)
    raw_result = record.get("result")
    error = record.get("error")

    safe_tool_output = clamp_tool_output(raw_result) if error is None else None

    if not TOOLS_CHAT_HYBRID_ENABLED or not is_hybrid:
        if error:
            output_text = f"[TOOL ERROR] {error}"
        else:
            output_text = f"[TOOL RESULT]\n{json.dumps(raw_result, indent=2, ensure_ascii=False)}"

        append_message(profile_id, chat_id, "user", prompt_text)
        append_message(profile_id, chat_id, "assistant", output_text)
        return {
            "output": output_text,
            "profile_id": profile_id,
            "chat_id": chat_id,
        }

    if error:
        tool_summary_prompt = (
            "You are an assistant explaining a failed tool call.\n\n"
            f"Tool name: {tool_name}\n"
            f"Error: {error}\n\n"
            "Explain in simple terms what went wrong and what the user can try."
        )
    else:
        tool_summary_prompt = (
            "You are an assistant summarizing the result of a local tool call "
            "for a non-technical user.\n\n"
            f"Tool name: {tool_name}\n"
            f"Raw result (JSON):\n{json.dumps(raw_result, indent=2, ensure_ascii=False)}\n\n"
            "Summarize the key points and suggest next steps."
        )

    summary = call_ollama(tool_summary_prompt, SMART_CHAT_MODEL_NAME)
    summary = clamp_chat_output(summary or "")

    append_message(profile_id, chat_id, "user", prompt_text)
    append_message(profile_id, chat_id, "assistant", summary)

    return {
        "output": summary,
        "profile_id": profile_id,
        "chat_id": chat_id,
    }


# =========================
# Vision-in-chat endpoint
# =========================


@router.post("/api/chat/vision")
async def api_chat_vision(
    profile_id: Optional[str] = Form(None),
    chat_id: Optional[str] = Form(None),
    prompt: str = Form(""),
    mode: str = Form("auto"),
    file: UploadFile = File(...),
):
    if not VISION_ENABLED:
        raise HTTPException(status_code=400, detail="Vision is disabled in config (VISION_ENABLED = False).")

    profile = _ensure_profile(profile_id)
    profile_id = profile["id"]

    chat_meta = _ensure_chat(profile_id, chat_id)
    chat_id = chat_meta["id"]

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="No image data received.")

    raw_prompt = prompt or ""
    safe_prompt = sanitize_chat_input(raw_prompt)

    vision_output = run_vision(
        image_bytes=image_bytes,
        user_prompt=safe_prompt,
        mode=mode or "auto",
    )

    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime = file.content_type or "image/png"
    user_msg_text = safe_prompt.strip() if safe_prompt else "(no prompt)"
    payload_text = "__IMG__%s|%s\n%s" % (mime, b64, user_msg_text)

    append_message(profile_id, chat_id, "user", payload_text)
    vision_output = clamp_chat_output(vision_output)
    append_message(profile_id, chat_id, "assistant", vision_output)

    history_logger.log(
        {
            "mode": "chat_vision_%s" % (mode or "auto"),
            "original_prompt": raw_prompt,
            "normalized_prompt": safe_prompt,
            "coder_output": None,
            "reviewer_output": None,
            "final_output": vision_output,
            "escalated": False,
            "escalation_reason": "",
            "judge": None,
            "chat_profile_id": profile_id,
            "chat_profile_name": profile.get("display_name"),
            "chat_id": chat_id,
            "chat_model_used": "vision",
            "models": {
                "vision": VISION_MODEL_NAME,
            },
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
# Profiles API
# =========================


@router.get("/api/chat/profiles")
def api_list_profiles():
    return {
        "profiles": list_profiles(),
    }


@router.post("/api/chat/profiles")
def api_create_profile(body: Dict[str, Any]):
    display_name = (body.get("display_name") or "").strip()
    if not display_name:
        display_name = "New Profile"
    model_override = (body.get("model_override") or "").strip() or None
    prof = create_profile(display_name=display_name, model_override=model_override)
    return prof


@router.patch("/api/chat/profiles/{profile_id}")
def api_update_profile(profile_id: str, body: ProfileUpdate):
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    display_name = body.display_name
    model_override = body.model_override

    if display_name is not None:
        rename_profile(profile_id, display_name)
        prof["display_name"] = display_name

    if model_override is not None:
        set_profile_model(profile_id, model_override)
        prof["model_override"] = model_override

    return prof


@router.delete("/api/chat/profiles/{profile_id}")
def api_delete_profile(profile_id: str):
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    delete_profile(profile_id)
    return {"ok": True}


# =========================
# Chats API
# =========================


@router.get("/api/chat/chats")
def api_list_chats(profile_id: str = Query(...)):
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    chats = list_chats(profile_id)
    return {
        "profile": prof,
        "chats": chats,
    }


@router.post("/api/chat/chats")
def api_create_chat(body: ChatCreate):
    prof = get_profile(body.profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    display_name = (body.display_name or "").strip()
    if not display_name:
        display_name = "New Chat"

    chat_meta = create_chat(
        profile_id=body.profile_id,
        display_name=display_name,
        model_override=body.model_override,
    )
    return chat_meta


@router.patch("/api/chat/chats/{profile_id}/{chat_id}")
def api_update_chat(profile_id: str, chat_id: str, body: ChatUpdate):
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    chat_meta = get_chat(profile_id, chat_id)
    if not chat_meta:
        raise HTTPException(status_code=404, detail="Chat not found")

    if body.display_name is not None:
        rename_chat(profile_id, chat_id, body.display_name)
        chat_meta["display_name"] = body.display_name

    if body.model_override is not None:
        set_chat_model(profile_id, chat_id, body.model_override)
        chat_meta["model_override"] = body.model_override

    return chat_meta


@router.delete("/api/chat/chats/{profile_id}/{chat_id}")
def api_delete_chat(profile_id: str, chat_id: str):
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    chat_meta = get_chat(profile_id, chat_id)
    if not chat_meta:
        raise HTTPException(status_code=404, detail="Chat not found")

    delete_chat(profile_id, chat_id)
    return {"ok": True}


# =========================
# Messages API
# =========================


@router.get("/api/chat/messages")
def api_get_messages(
    profile_id: str = Query(...),
    chat_id: str = Query(...),
):
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    chat_meta = get_chat(profile_id, chat_id)
    if not chat_meta:
        raise HTTPException(status_code=404, detail="Chat not found")

    msgs = get_messages(profile_id, chat_id)
    return {
        "profile": prof,
        "chat": chat_meta,
        "messages": msgs,
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

    raw_prompt = req.prompt or ""
    safe_prompt = sanitize_chat_input(raw_prompt)

    tool_response = _maybe_handle_tool_command(
        prompt_text=safe_prompt,
        req=req,
        profile=profile,
        profile_id=profile_id,
        chat_meta=chat_meta,
        chat_id=chat_id,
    )
    if tool_response is not None:
        return ChatResponse(
            output=tool_response["output"],
            profile_id=tool_response["profile_id"],
            chat_id=tool_response["chat_id"],
        )

    messages = get_messages(profile_id, chat_id)

    context_block = build_profile_context(profile_id, safe_prompt, max_snippets=8)

    from prompts import CHAT_SYSTEM_PROMPT

    base_model_name = _resolve_model(profile, chat_meta)
    profile_name = profile.get("display_name") or profile_id

    if req.smart:
        smart_result = run_chat_smart(
            profile=profile,
            profile_id=profile_id,
            chat_meta=chat_meta,
            chat_id=chat_id,
            messages=messages,
            user_prompt=safe_prompt,
            context_block=context_block,
        )
        answer = smart_result["answer"]
        model_name_used = smart_result["model_used"]
        judge_payload = smart_result.get("judge")
        smart_plan = smart_result.get("plan")
        mode_label = "chat_smart"
    else:
        convo_lines: List[str] = []
        for msg in messages:
            convo_lines.append(_render_message_for_prompt(msg))
        convo_lines.append("USER: %s" % safe_prompt)
        convo_block = "\n".join(convo_lines)

        if context_block:
            context_section = "Profile knowledge (saved notes):\n%s\n\n" % context_block
        else:
            context_section = ""

        full_prompt = """
%s

Current profile: %s

%sConversation so far:
%s

ASSISTANT:
""".strip() % (
            CHAT_SYSTEM_PROMPT,
            profile_name,
            context_section,
            convo_block,
        )

        model_name_used = base_model_name
        answer = call_ollama(full_prompt, model_name_used)
        judge_payload = None
        smart_plan = None
        mode_label = "chat"

    answer = clamp_chat_output(answer or "")

    append_message(profile_id, chat_id, "user", safe_prompt)
    append_message(profile_id, chat_id, "assistant", answer)

    history_logger.log(
        {
            "mode": mode_label,
            "original_prompt": raw_prompt,
            "normalized_prompt": safe_prompt,
            "coder_output": None,
            "reviewer_output": None,
            "final_output": answer,
            "escalated": False,
            "escalation_reason": "",
            "judge": judge_payload,
            "chat_profile_id": profile_id,
            "chat_profile_name": profile.get("display_name"),
            "chat_id": chat_id,
            "chat_model_used": model_name_used,
            "chat_smart_plan": smart_plan,
            "models": {
                "chat": model_name_used,
            },
        }
    )

    return ChatResponse(output=answer, profile_id=profile_id, chat_id=chat_id)


# =========================
# Profile summary API
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
        lines.append("[CHAT %s - %s]" % (cid, cname))
        msgs = get_messages(body.profile_id, cid) or []
        recent_msgs = msgs[-80:]
        for m in recent_msgs:
            ts = m.get("ts", "")
            role = (m.get("role") or "user").upper()
            text = m.get("text") or ""
            lines.append("%s %s: %s" % (ts, role, text))
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
""".strip()

    summary_prompt = "%s\n\nChats for this profile:\n\n%s" % (
        summary_system_prompt,
        raw_block,
    )

    summary_text = call_ollama(summary_prompt, SMART_CHAT_MODEL_NAME)

    return {
        "profile_id": body.profile_id,
        "summary": summary_text,
    }


# =========================
# Profile KB preview + note APIs
# =========================


@router.get("/api/chat/profile_kb_preview")
def api_profile_kb_preview(
    profile_id: str = Query(..., description="Profile ID"),
    limit: int = Query(20, ge=1, le=100, description="Max snippets to return"),
):
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    preview = build_profile_preview(profile_id, limit=limit)
    return preview


@router.post("/api/chat/profile_kb_note")
def api_profile_kb_note(body: KbNoteCreate):
    """
    Create a new KB note for a profile.

    Used by chat.html 'KB note' button.
    """
    profile_id = (body.profile_id or "").strip()
    title = (body.title or "").strip()
    content = (body.content or "").strip()

    if not profile_id:
        raise HTTPException(status_code=400, detail="Missing profile_id")
    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    if not title:
        title = "Note"

    if not content:
        raise HTTPException(status_code=400, detail="Note content is empty")

    snippet_id = add_snippet(profile_id, title, content)
    if snippet_id <= 0:
        raise HTTPException(status_code=400, detail="Failed to insert note")

    preview = build_profile_preview(profile_id, limit=20)
    return {
        "ok": True,
        "profile_id": profile_id,
        "snippet_id": snippet_id,
        "preview": preview,
    }


@router.delete("/api/chat/profile_kb/{snippet_id}")
def api_profile_kb_delete(snippet_id: int):
    """
    Delete a KB note by ID and return updated preview for its profile.
    """
    snippet = get_snippet(snippet_id)
    if not snippet:
        raise HTTPException(status_code=404, detail="KB note not found")

    profile_id = snippet["profile_id"]
    deleted = delete_snippet(snippet_id)
    if not deleted:
        raise HTTPException(status_code=400, detail="KB delete failed")

    preview = build_profile_preview(profile_id, limit=20)
    return {
        "ok": True,
        "profile_id": profile_id,
        "preview": preview,
    }
