"""
chat_ui.py

Chat workspace API (multi-profile, multi-chat) for the Personal Local AI OS.

Features:
- Profiles (per-project / per-context workspaces)
- Chats inside profiles
- Normal vs Smart chat modes
- Vision-in-chat (image upload + LLaVA)
- Tool commands in chat:
    ///tool TOOL_NAME
    { "arg": "value" }

    ///tool+chat TOOL_NAME
    { "arg": "value" }

Normal vs Smart:
- normal → uses CHAT_MODEL_NAME (or overrides), single model call
- smart  → uses SMART_CHAT_MODEL_NAME and runs planner → answer → judge
           via chat_pipeline.run_chat_smart

This file exposes the FastAPI router mounted by code_server.py as `chat_router`.
"""

import base64
import json
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel

from config import (
    CHAT_MODEL_NAME,
    AVAILABLE_MODELS,
    VISION_ENABLED,
    SMART_CHAT_MODEL_NAME,
    TOOLS_IN_CHAT_ENABLED,
    TOOLS_CHAT_HYBRID_ENABLED,
)
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
from tools_runtime import execute_tool
from chat_pipeline import run_chat_smart
from profile_kb import build_profile_context

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
    smart: Optional[bool] = False  # when True, use smart chat pipeline


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
    """
    Resolve or auto-create a profile.

    - If profile_id is None:
        - return first existing profile if any
        - else create a new default profile
    - If profile_id is provided but missing in DB -> 404
    """
    profiles = list_profiles()

    if not profile_id:
        if profiles:
            return profiles[0]
        return create_profile(display_name=None, model_override=None)

    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile '%s' not found" % profile_id)
    return prof


def _ensure_chat(profile_id: str, chat_id: Optional[str]) -> Dict[str, Any]:
    """
    Resolve or auto-create a chat in a given profile.

    - If chat_id is None:
        - return first existing chat if any
        - else create a new default chat
    - If chat_id is provided but missing:
        - create a new chat whose display_name defaults to chat_id
    """
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
    """
    Decide which model to use for a chat turn (base model).

    Precedence:
    - chat.model_override
    - profile.model_override
    - CHAT_MODEL_NAME (default from config)
    """
    chat_model = chat.get("model_override")
    if chat_model:
        return chat_model

    prof_model = profile.get("model_override")
    if prof_model:
        return prof_model

    return CHAT_MODEL_NAME


def _render_message_for_prompt(msg: Dict[str, Any]) -> str:
    """
    Render a stored chat message into a compact text line for the LLM prompt.

    Special handling for vision messages:

      __IMG__<mime>|<base64>\n<caption>

    We strip the base64 blob entirely and keep only a short marker + caption so
    the model understands an image was involved, without polluting the prompt.
    """
    role = (msg.get("role") or "user").upper()
    text = msg.get("text") or ""

    if text.startswith("__IMG__"):
        # Format: __IMG__{mime}|{b64}\n{caption}
        lines = text.splitlines()
        caption = ""
        if len(lines) > 1:
            caption = "\n".join(lines[1:]).strip()

        if caption:
            return "%s (image): (caption: %s)" % (role, caption)
        return "%s (image): (no caption, image attached)" % role

    return "%s: %s" % (role, text)


def _maybe_handle_tool_command(
    req: ChatRequest,
    profile: Dict[str, Any],
    profile_id: str,
    chat_meta: Dict[str, Any],
    chat_id: str,
):
    """
    Handle explicit tool commands in chat.

    Supported syntaxes:

        ///tool TOOL_NAME
        {"arg1": "...", "arg2": 123}

        ///tool+chat TOOL_NAME
        {"arg1": "..."}

    - "///tool"      -> execute tool and return raw JSON/text result
    - "///tool+chat" -> if TOOLS_CHAT_HYBRID_ENABLED is True, execute tool AND
                        let the chat model summarize the result for the user.
                        If the flag is False, falls back to raw JSON result.

    If TOOLS_IN_CHAT_ENABLED is False, this function always returns None.
    """
    if not TOOLS_IN_CHAT_ENABLED:
        return None

    text = req.prompt or ""
    stripped = text.lstrip()

    if not stripped.startswith("///tool"):
        return None

    try:
        lines = stripped.splitlines()
        first_line = lines[0].strip()

        hybrid_requested = first_line.startswith("///tool+chat")
        if hybrid_requested:
            prefix = "///tool+chat"
        else:
            prefix = "///tool"

        remainder = first_line[len(prefix):].strip()
        if not remainder:
            error_msg = (
                "Tool command format:\n"
                "  ///tool TOOL_NAME\n"
                "  {\"optional\": \"json args\"}\n\n"
                "Hybrid mode:\n"
                "  ///tool+chat TOOL_NAME\n"
                "  {\"optional\": \"json args\"}\n"
            )
            append_message(profile_id, chat_id, "user", req.prompt)
            append_message(profile_id, chat_id, "assistant", error_msg)
            history_logger.log(
                {
                    "mode": "chat_tool_error",
                    "original_prompt": req.prompt,
                    "normalized_prompt": req.prompt,
                    "coder_output": None,
                    "reviewer_output": None,
                    "final_output": error_msg,
                    "escalated": False,
                    "escalation_reason": "",
                    "judge": None,
                    "chat_profile_id": profile_id,
                    "chat_profile_name": profile.get("display_name"),
                    "chat_id": chat_id,
                    "chat_model_used": "tool_command",
                }
            )
            return {
                "output": error_msg,
                "profile_id": profile_id,
                "chat_id": chat_id,
            }

        tool_name = remainder
        args: Dict[str, Any] = {}

        if len(lines) > 1:
            raw_args = "\n".join(lines[1:]).strip()
            if raw_args:
                parsed = json.loads(raw_args)
                if isinstance(parsed, dict):
                    args = parsed
                else:
                    raise ValueError("Tool args JSON must be an object/dict.")

        context = {
            "source": "chat_tool",
            "profile_id": profile_id,
            "chat_id": chat_id,
            "profile_name": profile.get("display_name"),
            "chat_display_name": chat_meta.get("display_name"),
        }

        record = execute_tool(tool_name, args, context)

        if record.get("ok"):
            result = record.get("result")
            if result is None:
                raw_result_text = "(tool executed successfully, but returned no result)"
            else:
                try:
                    raw_result_text = json.dumps(result, ensure_ascii=False, indent=2)
                except Exception:
                    raw_result_text = str(result)
        else:
            raw_result_text = "Tool '%s' failed: %s" % (
                tool_name,
                record.get("error") or "Unknown error",
            )

        output_text = raw_result_text
        mode_label = "chat_tool_execution"

        if (
            hybrid_requested
            and TOOLS_CHAT_HYBRID_ENABLED
            and record.get("ok")
        ):
            try:
                summary_prompt = """
You are an assistant summarizing the result of a tool execution for the user.

Tool name: %s

Original user message:
%s

Raw tool result (JSON or text):
%s

Explain the result in clear, concise natural language. If there are numeric values
or statuses, interpret them briefly. Do NOT include the raw JSON in your answer.
""".strip() % (tool_name, req.prompt, raw_result_text)

                summary = call_ollama(summary_prompt, SMART_CHAT_MODEL_NAME)
                summary = (summary or "").strip()
                if summary:
                    output_text = summary
                    mode_label = "chat_tool_hybrid"
            except Exception as e:
                fallback_msg = "(Hybrid summarization failed: %s. Showing raw tool result instead.)\n\n%s" % (
                    str(e),
                    raw_result_text,
                )
                output_text = fallback_msg
                mode_label = "chat_tool_hybrid"

        append_message(profile_id, chat_id, "user", req.prompt)
        append_message(profile_id, chat_id, "assistant", output_text)

        history_logger.log(
            {
                "mode": mode_label,
                "original_prompt": req.prompt,
                "normalized_prompt": req.prompt,
                "coder_output": None,
                "reviewer_output": None,
                "final_output": output_text,
                "escalated": False,
                "escalation_reason": "",
                "judge": None,
                "chat_profile_id": profile_id,
                "chat_profile_name": profile.get("display_name"),
                "chat_id": chat_id,
                "chat_model_used": "tool_command",
                "tool_record": record,
            }
        )

        return {
            "output": output_text,
            "profile_id": profile_id,
            "chat_id": chat_id,
        }

    except Exception as e:
        error_msg = "Tool command handling failed: %s" % str(e)
        append_message(profile_id, chat_id, "user", req.prompt)
        append_message(profile_id, chat_id, "assistant", error_msg)
        history_logger.log(
            {
                "mode": "chat_tool_error",
                "original_prompt": req.prompt,
                "normalized_prompt": req.prompt,
                "coder_output": None,
                "reviewer_output": None,
                "final_output": error_msg,
                "escalated": False,
                "escalation_reason": "",
                "judge": None,
                "chat_profile_id": profile_id,
                "chat_profile_name": profile.get("display_name"),
                "chat_id": chat_id,
                "chat_model_used": "tool_command",
            }
        )
        return {
            "output": error_msg,
            "profile_id": profile_id,
            "chat_id": chat_id,
        }


# =========================
# Profile management API
# =========================

@router.get("/api/chat/profiles")
def api_list_profiles():
    return {"profiles": list_profiles()}


@router.post("/api/chat/profiles")
def api_create_profile_endpoint(body: ProfileCreate):
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
def api_delete_profile_endpoint(profile_id: str):
    ok = delete_profile(profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profile not found or could not be deleted")
    return {"ok": True}


# =========================
# Chat management API
# =========================

@router.get("/api/chat/chats")
def api_list_chats(
    profile_id: str = Query(..., description="Profile ID to list chats for"),
):
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
def api_get_messages(
    profile_id: str = Query(..., description="Profile ID"),
    chat_id: str = Query(..., description="Chat ID"),
):
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

    vision_output = run_vision(
        image_bytes=image_bytes,
        user_prompt=prompt or "",
        mode=mode or "auto",
    )

    mime = file.content_type or "image/png"
    if not mime.startswith("image/"):
        mime = "image/png"
    b64 = base64.b64encode(image_bytes).decode("ascii")

    user_msg_text = prompt.strip() if prompt else "(no prompt)"
    payload_text = "__IMG__%s|%s\n%s" % (mime, b64, user_msg_text)

    append_message(profile_id, chat_id, "user", payload_text)
    append_message(profile_id, chat_id, "assistant", vision_output)

    history_logger.log(
        {
            "mode": "chat_vision_%s" % (mode or "auto"),
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
    """
    Main chat endpoint used by chat.html.

    Flow:
    - Resolve / create profile + chat
    - If prompt starts with ///tool or ///tool+chat -> handle via tools runtime
    - Else:
        - NORMAL (smart=False):
            - Single model call using base model, with optional profile context
        - SMART (smart=True):
            - Use chat_pipeline.run_chat_smart (planner → answer → judge),
              with optional profile context
        - Append user + assistant messages
        - Log into history (including judge info for smart mode)
    """
    profile = _ensure_profile(req.profile_id)
    profile_id = profile["id"]

    chat_meta = _ensure_chat(profile_id, req.chat_id)
    chat_id = chat_meta["id"]

    # Tool-command interception BEFORE any LLM chat pipeline
    tool_response = _maybe_handle_tool_command(
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

    # Build optional profile-aware context block from KB
    # Uses current prompt text as a loose "query" for relevance.
    context_block = build_profile_context(profile_id, req.prompt or "", max_snippets=8)

    from prompts import CHAT_SYSTEM_PROMPT

    base_model_name = _resolve_model(profile, chat_meta)
    profile_name = profile.get("display_name") or profile_id

    # Decide smart vs normal path
    if req.smart:
        # SMART CHAT PIPELINE (planner → answer → judge), with context injected
        smart_result = run_chat_smart(
            profile=profile,
            profile_id=profile_id,
            chat_meta=chat_meta,
            chat_id=chat_id,
            messages=messages,
            user_prompt=req.prompt,
            context_block=context_block,
        )
        answer = smart_result["answer"]
        model_name_used = smart_result["model_used"]
        judge_payload = smart_result.get("judge")
        smart_plan = smart_result.get("plan")
        mode_label = "chat_smart"
    else:
        # NORMAL CHAT (single call, optionally with profile context)
        convo_lines: List[str] = []
        for msg in messages:
            convo_lines.append(_render_message_for_prompt(msg))
        convo_lines.append("USER: %s" % req.prompt)
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

    # Persist messages
    append_message(profile_id, chat_id, "user", req.prompt)
    append_message(profile_id, chat_id, "assistant", answer)

    # Log to history for dashboard/trace
    history_logger.log(
        {
            "mode": mode_label,
            "original_prompt": req.prompt,
            "normalized_prompt": req.prompt,
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
            # Extra field for smart mode; harmless for normal mode
            "chat_smart_plan": smart_plan,
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
