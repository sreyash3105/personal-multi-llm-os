"""
Chat UI core functions for multi-profile chat workspace.

Responsibilities:
- Multi-profile, multi-chat text workspace
- Chat execution functions (normal + smart chat)
- Vision-in-chat execution
- Tools in chat (///tool + args)
- Simple profile/chat/messages CRUD operations
- Profile KB preview + note creation / deletion + search + auto-notes

This module is "sacred" in V3.x — only incremental, low-risk edits allowed.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional

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
    extract_json_object,
)


class ChatRequest:
    profile_id: Optional[str] = None
    chat_id: Optional[str] = None
    prompt: str = ""
    smart: bool = False

    def __init__(self, profile_id: Optional[str] = None, chat_id: Optional[str] = None, prompt: str = "", smart: bool = False):
        self.profile_id = profile_id
        self.chat_id = chat_id
        self.prompt = prompt
        self.smart = smart


def handle_chat_turn(profile_id: str, chat_id: str, prompt: str, smart: bool = False):
    """
    Handle a chat turn for given profile and chat.
    """
    profile = _ensure_profile(profile_id)
    profile_id = profile["id"]

    chat_meta = _ensure_chat(profile_id, chat_id)
    chat_id = chat_meta["id"]

    raw_prompt = prompt or ""
    safe_prompt = sanitize_chat_input(raw_prompt)

    tool_response = _maybe_handle_tool_command(
        prompt_text=safe_prompt,
        req=ChatRequest(profile_id=profile_id, chat_id=chat_id, prompt=prompt, smart=smart),
        profile=profile,
        profile_id=profile_id,
        chat_meta=chat_meta,
        chat_id=chat_id,
    )
    if tool_response is not None:
        return tool_response

    messages = get_messages(profile_id, chat_id)
    context_block = build_profile_context(profile_id, safe_prompt, max_snippets=8)

    base_model_name = _resolve_model(profile, chat_meta)
    profile_name = profile.get("display_name") or profile_id

    if smart:
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
        judge_payload = smart_result.get("judge") if isinstance(smart_result.get("judge"), dict) else None
        model_name_used = smart_result.get("model_used") or base_model_name
        smart_plan = str(smart_result.get("plan")) if smart_result.get("plan") else None
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

    return {"output": answer, "profile_id": profile_id, "chat_id": chat_id}


def _ensure_profile(profile_id: Optional[str]) -> Dict[str, Any]:
    """
    Ensure a valid profile exists.
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
    Ensure there is a chat for given profile.
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
    Render a stored message into a prompt line for model.
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
    """
    name = tool_record.get("tool") or "unknown"
    ok = bool(tool_record.get("ok"))
    error = tool_record.get("error")
    result = tool_record.get("result")

    header = f"[tool:{name}] "

    if not ok:
        return header + f"FAILED: {error or 'unknown error'}"

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
        output_text = _render_tool_result_text(tool_record)
        append_message(profile_id, chat_id, "user", prompt_text)
        append_message(profile_id, chat_id, "assistant", output_text)
        return {
            "output": output_text,
            "profile_id": profile_id,
            "chat_id": chat_id,
        }

    summary_prompt = """
%s

You are assisting inside a local developer tools workspace.

A tool was just executed.

Tool name: %s
Tool call args (JSON): %s

Tool record:
%s

Write a short, clear reply to user explaining what happened,
what result means, and any next steps. Do NOT show raw JSON unless needed.
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
