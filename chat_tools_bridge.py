"""
Bridge between raw chat model output and local tools.

V1 design (safe & simple):
- If the model's ENTIRE output parses as a JSON object with:
    {"tool": "<name>", "args": {...}, "assistant_comment": "<optional text>"}
  then:
    - run the matching tool from TOOL_REGISTRY
    - compose a final answer mixing assistant_comment + tool result
    - return (final_answer, tool_meta)

- Otherwise:
    - return (raw_answer, None)

This means:
- Normal text answers are untouched.
- Tools only run when the model (or user) explicitly returns valid JSON.
"""

import json
from typing import Tuple, Optional, Dict, Any

from file_tools import TOOL_REGISTRY


def _try_parse_tool_call(raw: str) -> Optional[Dict[str, Any]]:
    raw = (raw or "").strip()
    if not raw:
        return None

    # Only treat as tool call if the whole reply is JSON
    try:
        data = json.loads(raw)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    name = data.get("tool")
    args = data.get("args")
    if not isinstance(name, str) or not isinstance(args, dict):
        return None

    return data


def process_chat_model_output(
    raw_answer: str,
    profile_id: str,
    chat_id: str,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Entry point used by chat_ui.api_chat.

    Returns:
      final_answer: str      # what gets stored in chat + shown to user
      tool_meta: dict|None   # metadata persisted in history_logger
    """
    # 1) Try to interpret as a tool call
    call = _try_parse_tool_call(raw_answer)
    if not call:
        # No tool invocation detected: pass through
        return raw_answer, None

    tool_name = call.get("tool")
    args = call.get("args") or {}
    assistant_comment = (call.get("assistant_comment") or "").strip()

    # Inject profile/chat IDs so tools can use them
    args.setdefault("profile_id", profile_id)
    args.setdefault("chat_id", chat_id)

    tool_fn = TOOL_REGISTRY.get(tool_name)
    if not tool_fn:
        # Unknown tool: return a gentle message instead of crashing
        final = (
            assistant_comment + "\n\n"
            if assistant_comment
            else ""
        ) + f"(Tool error: unknown tool '{tool_name}'. Raw reply was: {raw_answer})"
        meta = {
            "tool": tool_name,
            "args": args,
            "error": "unknown_tool",
        }
        return final, meta

    try:
        result = tool_fn(args)
    except Exception as e:
        final = (
            assistant_comment + "\n\n"
            if assistant_comment
            else ""
        ) + f"(Tool execution error: {e})"
        meta = {
            "tool": tool_name,
            "args": args,
            "error": "execution_error",
            "exception": str(e),
        }
        return final, meta

    ok = bool(result.get("ok"))
    msg = (result.get("message") or "").strip()

    if assistant_comment:
        if msg:
            final_answer = assistant_comment + "\n\n" + msg
        else:
            final_answer = assistant_comment
    else:
        final_answer = msg or "(Tool executed, but returned no message.)"

    tool_meta = {
        "tool": tool_name,
        "args": args,
        "ok": ok,
        "raw_result": result,
    }
    return final_answer, tool_meta
