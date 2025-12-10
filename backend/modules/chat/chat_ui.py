"""
Chat UI + API layer for multi-profile chat workspace.

Responsibilities:
- Multi-profile, multi-chat text workspace
- Main /api/chat endpoint (normal + smart chat)
- Vision-in-chat endpoint
- Tools in chat (///tool + args)
- Simple profile/chat/messages CRUD for static/chat.html
- Profile KB preview + note creation / deletion + search + auto-notes

This module is "sacred" in V3.x — only incremental, low-risk edits allowed.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from pydantic import BaseModel

from backend.core.config import (
    CHAT_MODEL_NAME,
    SMART_CHAT_MODEL_NAME,
    AVAILABLE_MODELS,
    VISION_ENABLED,
    TOOLS_IN_CHAT_ENABLED,
    TOOLS_CHAT_HYBRID_ENABLED,
    VISION_MODEL_NAME,
)
from backend.modules.telemetry.history import history_logger
from backend.modules.code.pipeline import call_ollama
# add with other backend.modules imports
from backend.modules.router.router import route_request

from backend.modules.code.prompts import CHAT_SYSTEM_PROMPT
from backend.modules.kb.profile_kb import (
    build_profile_context,
    build_profile_preview,
    add_snippet,
    delete_snippet,
    get_snippet,
    search_snippets,
)
from backend.modules.tools.tools_runtime import execute_tool
from backend.modules.chat.chat_pipeline import run_chat_smart
from backend.modules.vision.vision_pipeline import run_vision
from backend.modules.chat.chat_storage import (
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
from backend.modules.common.io_guards import (
    sanitize_chat_input,
    clamp_chat_output,
    clamp_tool_output,
)

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


class AutoKbNoteRequest(BaseModel):
    """
    Request payload for auto-generating a KB note from a single chat.

    Fields:
      - profile_id: profile whose chat we’re summarizing
      - chat_id: chat id within that profile
      - max_messages: how many recent messages to consider (10–200)
      - title_hint: optional hint for the note title
    """
    profile_id: str
    chat_id: str
    max_messages: int = 80
    title_hint: Optional[str] = None


# =========================
# Internal helpers
# =========================


def _ensure_profile(profile_id: Optional[str]) -> Dict[str, Any]:
    """
    Ensure a valid profile exists.

    - If profile_id is provided and exists, return it.
    - If profile_id is missing or invalid, auto-select first profile
      or create a "Default" profile.
    """
    if profile_id:
        prof = get_profile(profile_id)
        if prof:
            return prof

    profiles = list_profiles()
    if profiles:
        return profiles[0]

    # Auto-create a default profile
    prof = create_profile(display_name="Default", model_override=None)
    return prof


def _ensure_chat(profile_id: str, chat_id: Optional[str]) -> Dict[str, Any]:
    """
    Ensure there is a chat for the given profile.

    - If chat_id is provided and exists, return it.
    - Otherwise, create a new chat titled "New Chat".
    """
    if chat_id:
        meta = get_chat(profile_id, chat_id)
        if meta:
            return meta

    chats = list_chats(profile_id)
    if chats:
        return chats[0]

    chat_meta = create_chat(profile_id=profile_id, display_name="New Chat", model_override=None)
    return chat_meta


def _resolve_model(profile: Dict[str, Any], chat_meta: Dict[str, Any]) -> str:
    """
    Resolve which model to use for this chat.

    Priority:
      1) chat.model_override
      2) profile.model_override
      3) CHAT_MODEL_NAME (global default)
    """
    chat_override = (chat_meta.get("model_override") or "").strip()
    if chat_override:
        return chat_override

    prof_override = (profile.get("model_override") or "").strip()
    if prof_override:
        return prof_override

    return CHAT_MODEL_NAME


def _render_message_for_prompt(msg: Dict[str, Any]) -> str:
    """
    Render a stored message into a prompt line for the model.
    """
    role = (msg.get("role") or "user").upper()
    text = msg.get("text") or ""
    ts = msg.get("ts") or ""
    if ts:
        return "%s %s: %s" % (ts, role, text)
    return "%s: %s" % (role, text)


def _render_tool_result_text(tool_record: Dict[str, Any]) -> str:
    """
    Render a tool_record from tools_runtime.execute_tool into a short
    human-readable snippet for chat.

    This is used when the user runs ///tool in chat and wants to see
    raw-ish results, but not full JSON.
    """
    name = tool_record.get("tool") or "unknown"
    ok = bool(tool_record.get("ok"))
    error = tool_record.get("error")
    result = tool_record.get("result")

    header = f"[tool:{name}] "

    if not ok:
        return header + f"FAILED: {error or 'unknown error'}"

    # Clamp result for safety in chat
    pretty_result = clamp_tool_output(result)
    return header + f"OK\n{pretty_result}"


def _maybe_handle_tool_command(
    prompt_text: str,
    req: ChatRequest,
    profile: Dict[str, Any],
    profile_id: str,
    chat_meta: Dict[str, Any],
    chat_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Detect and handle ///tool and ///tool+chat commands inside chat.

    Returns:
      - dict with {output, profile_id, chat_id} if handled
      - None if normal chat should proceed
    """
    if not TOOLS_IN_CHAT_ENABLED:
        return None

    text = (prompt_text or "").strip()
    if not text.startswith("///tool"):
        return None

    is_hybrid = False
    first_line, *rest_lines = text.split("\n", 1)
    if first_line.startswith("///tool+chat"):
        is_hybrid = True
        cmd_body = first_line[len("///tool+chat") :].strip()
    else:
        cmd_body = first_line[len("///tool") :].strip()

    if not cmd_body:
        return {
            "output": "[tools] Usage: ///tool TOOL_NAME {\"arg\": \"value\"} or ///tool+chat ...",
            "profile_id": profile_id,
            "chat_id": chat_id,
        }

    parts = cmd_body.split(" ", 1)
    tool_name = parts[0].strip()
    args_raw = parts[1].strip() if len(parts) > 1 else ""

    if not tool_name:
        return {
            "output": "[tools] Missing tool name after ///tool",
            "profile_id": profile_id,
            "chat_id": chat_id,
        }

    if args_raw:
        try:
            tool_args = json.loads(args_raw)
            if not isinstance(tool_args, dict):
                raise ValueError("Tool args must be a JSON object")
        except Exception as exc:
            return {
                "output": f"[tools] Failed to parse JSON args: {exc}",
                "profile_id": profile_id,
                "chat_id": chat_id,
            }
    else:
        tool_args = {}

    context = {
        "source": "chat",
        "profile_id": profile_id,
        "chat_id": chat_id,
    }

    tool_record = execute_tool(tool_name, tool_args, context=context)

    # Log the tool call into history regardless of hybrid vs non-hybrid
    safe_tool_output = clamp_tool_output(tool_record.get("result"))
    history_logger.log(
        {
            "mode": "chat_tool_hybrid" if is_hybrid else "chat_tool",
            "original_prompt": prompt_text,
            "normalized_prompt": prompt_text,
            "coder_output": None,
            "reviewer_output": None,
            "final_output": safe_tool_output,
            "escalated": False,
            "escalation_reason": "",
            "judge": None,
            "chat_profile_id": profile_id,
            "chat_profile_name": profile.get("display_name"),
            "chat_id": chat_id,
            "chat_model_used": None,
            "chat_smart_plan": None,
            "models": {
                "tool": tool_name,
            },
            "tool_record": tool_record,
        }
    )

    if not is_hybrid or not TOOLS_CHAT_HYBRID_ENABLED:
        # Simple mode: just show tool result inline
        output_text = _render_tool_result_text(tool_record)
        append_message(profile_id, chat_id, "user", prompt_text)
        append_message(profile_id, chat_id, "assistant", output_text)
        return {
            "output": output_text,
            "profile_id": profile_id,
            "chat_id": chat_id,
        }

    # Hybrid: ask chat model to summarize tool_result for the user
    summary_prompt = """
%s

You are assisting inside a local developer tools workspace.

A tool was just executed.

Tool name: %s
Tool call args (JSON): %s

Tool record:
%s

Write a short, clear reply to the user explaining what happened,
what the result means, and any next steps. Do NOT show raw JSON unless needed.
""" % (
        CHAT_SYSTEM_PROMPT,
        tool_name,
        json.dumps(tool_args, ensure_ascii=False),
        json.dumps(tool_record, ensure_ascii=False),
    )

    summary_answer = call_ollama(summary_prompt, SMART_CHAT_MODEL_NAME)
    summary_answer = clamp_chat_output(summary_answer or "")

    append_message(profile_id, chat_id, "user", prompt_text)
    append_message(profile_id, chat_id, "assistant", summary_answer)

    return {
        "output": summary_answer,
        "profile_id": profile_id,
        "chat_id": chat_id,
    }


# =========================
# Vision-in-chat API
# =========================


@router.post("/api/chat", response_model=ChatResponse)
def api_chat(req: ChatRequest):
    """
    Main /api/chat endpoint (router-first).
    This function preserves all previous behavior but asks the router first
    so commands, tools, code, automation can be intercepted safely.
    """
    profile = _ensure_profile(req.profile_id)
    profile_id = profile["id"]

    chat_meta = _ensure_chat(profile_id, req.chat_id)
    chat_id = chat_meta["id"]

    raw_prompt = req.prompt or ""
    safe_prompt = sanitize_chat_input(raw_prompt)

    # 1) existing ///tool handling (keep this as-is)
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

    # 2) Router-first: classify and (optionally) route before invoking chat pipeline
    routed = None
    try:
        # route_request should not execute risky ops by default from UI; execute=False
        routed = route_request({
            "text": safe_prompt,
            "profile_id": profile_id,
            "chat_id": chat_id,
            "source": "chat",
            "execute": False,
        })
    except Exception as e:
        # If router fails for any reason, fallback to chat pipeline so UI doesn't break.
        # We log the exception into history for debugging.
        try:
            history_logger.log(
                {
                    "mode": "router_error",
                    "original_prompt": raw_prompt,
                    "normalized_prompt": safe_prompt,
                    "final_output": str(e),
                    "chat_profile_id": profile_id,
                    "chat_id": chat_id,
                }
            )
        except Exception:
            pass
        routed = {"intent": "chat", "confidence": 0.0, "action": "chat", "result": None}

    # 3) If router decided not to route to chat, return router result to UI
    if routed.get("action") and routed.get("action") != "chat":
        rr = routed.get("result", {})
        # extract a friendly textual output
        if isinstance(rr, dict) and "output" in rr:
            out_text = rr.get("output")
        elif isinstance(rr, dict) and "message" in rr:
            out_text = rr.get("message")
        elif isinstance(rr, dict) and "final_output" in rr:
            out_text = rr.get("final_output")
        else:
            try:
                out_text = json.dumps(rr, ensure_ascii=False)
            except Exception:
                out_text = str(rr)

        # Append messages only if router indicates it executed something that should be in history
        try:
            append_message(profile_id, chat_id, "user", safe_prompt)
            append_message(profile_id, chat_id, "assistant", out_text)
        except Exception:
            # don't break the response on append failure
            pass

        return ChatResponse(
            output=out_text or "[routed action executed]",
            profile_id=profile_id,
            chat_id=chat_id,
        )

    # 4) Otherwise, fall back to chat flow (router may have already prepared result)
    messages = get_messages(profile_id, chat_id)
    context_block = build_profile_context(profile_id, safe_prompt, max_snippets=8)

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
        answer = smart_result.get("answer") or ""
        judge_payload = smart_result.get("judge")
        model_name_used = smart_result.get("model_used") or base_model_name
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
        answer = smart_result.get("answer") or ""
        judge_payload = smart_result.get("judge")
        model_name_used = smart_result.get("model_used") or base_model_name
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
# Auto KB note from a single chat
# =========================


@router.post("/api/chat/profile_kb_auto")
def api_profile_kb_auto(body: AutoKbNoteRequest):
    """
    Turn the recent messages of a single chat into a KB note (auto-notes).

    This does NOT mutate chat; it only creates a new profile_snippets entry.
    """
    profile = get_profile(body.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    chat_meta = get_chat(body.profile_id, body.chat_id)
    if not chat_meta:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Clamp how many messages we read
    try:
        max_messages = int(body.max_messages or 80)
    except Exception:
        max_messages = 80
    max_messages = max(10, min(max_messages, 200))

    msgs = get_messages(body.profile_id, body.chat_id) or []
    if not msgs:
        return {
            "ok": False,
            "message": "This chat has no messages yet; nothing to save.",
        }

    recent = msgs[-max_messages:]
    lines: List[str] = []
    for m in recent:
        ts = m.get("ts", "")
        role = (m.get("role") or "user").upper()
        text = m.get("text") or ""
        lines.append("%s %s: %s" % (ts, role, text))

    convo_block = "\n".join(lines)

    system_prompt = """
You are helping a developer turn a chat transcript into a reusable knowledge-base note.

Transcript (most recent messages last) is provided below.

Your job:
1) Extract only durable facts, decisions, configs, and TODOs that will matter later.
2) Ignore greetings, smalltalk, and dead-ends.
3) Be concrete: include file names, endpoints, flags, commands, and important values when present.
4) Output STRICT JSON ONLY with this shape:

{
  "title": "<short descriptive title>",
  "content": "<2-8 bullet points or short paragraphs capturing the key decisions and facts>"
}

If there is clearly nothing useful to save, output:

{
  "title": "SKIP",
  "content": ""
}
""".strip()

    prompt = "%s\n\nTRANSCRIPT:\n%s" % (system_prompt, convo_block)
    model_name = SMART_CHAT_MODEL_NAME

    def _fallback(auto_mode: str, error_text: Optional[str]) -> Dict[str, Any]:
        fallback_title = (body.title_hint or "").strip() or f"Auto note from chat {body.chat_id}"
        fallback_content = "Auto-generated note from recent chat messages.\n\n" + convo_block
        note_id = add_snippet(body.profile_id, fallback_title, fallback_content)
        return {
            "ok": True,
            "profile_id": body.profile_id,
            "chat_id": body.chat_id,
            "note_id": note_id,
            "title": fallback_title,
            "content": fallback_content,
            "model_used": model_name,
            "auto_mode": auto_mode,
            "error": error_text,
        }

    try:
        raw = call_ollama(prompt, model_name) or ""
    except Exception as e:
        return _fallback(auto_mode="fallback_exception", error_text=str(e))

    raw = str(raw).strip()
    # Try to isolate the JSON object if model wrapped it in text
    candidate = raw
    if "{" in candidate and "}" in candidate:
        candidate = candidate[candidate.find("{") : candidate.rfind("}") + 1]

    try:
        data = json.loads(candidate)
    except Exception as e:
        return _fallback(auto_mode="fallback_parse_error", error_text=str(e))

    title = str(data.get("title") or "").strip()
    content = str(data.get("content") or "").strip()

    if title.upper() == "SKIP" or not content:
        return {
            "ok": False,
            "message": "Model suggested skipping auto-note (no durable content detected).",
            "model_used": model_name,
        }

    if not title:
        title = (body.title_hint or "").strip() or f"Auto note from chat {body.chat_id}"

    note_id = add_snippet(body.profile_id, title, content)
    if not note_id:
        return {
            "ok": False,
            "message": "Failed to create KB note.",
            "model_used": model_name,
        }

    # Optional: emit a small history record so it shows up in the dashboard
    try:
        history_logger.log(
            {
                "mode": "profile_kb_auto_note",
                "kind": "kb_note",
                "chat_profile_id": body.profile_id,
                "chat_id": body.chat_id,
                "original_prompt": "(auto KB note from chat)",
                "normalized_prompt": "",
                "final_output": content,
                "kb_note_id": note_id,
                "kb_note_title": title,
                "model_used": model_name,
            }
        )
    except Exception:
        pass

    return {
        "ok": True,
        "message": f"Created KB note #{note_id} from chat {body.chat_id}.",
        "profile_id": body.profile_id,
        "chat_id": body.chat_id,
        "note_id": note_id,
        "title": title,
        "content": content,
        "model_used": model_name,
        "auto_mode": "structured",
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


@router.get("/api/chat/profile_kb_search")
def api_profile_kb_search(
    profile_id: str = Query(..., description="Profile ID"),
    query: str = Query(..., description="Search query string"),
    limit: int = Query(20, ge=1, le=100, description="Max snippets to return"),
):
    """
    Search KB notes for a profile by simple keyword query.

    This is a lightweight wrapper around profile_kb.search_snippets.
    It does NOT modify data; read-only and safe for UI search panels.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        raise HTTPException(status_code=400, detail="Missing profile_id")

    prof = get_profile(profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")

    q = (query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Missing query")

    snippets = search_snippets(profile_id, q, limit=limit)

    return {
        "profile_id": profile_id,
        "query": q,
        "total": len(snippets),
        "snippets": snippets,
    }
