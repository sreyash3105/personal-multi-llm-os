"""
io_guards.py

Shared input/output size guardrails for chat, tools, and other pipelines.

This module complements the size guards already present in pipeline.py and
vision_pipeline.py by providing reusable helpers for:

- Chat input sanitization
- Chat output clamping
- Tool output clamping

No existing code is modified yet; this is a library module only.
"""

from __future__ import annotations

import json
from typing import Any


# These values are conservative defaults for V3.4.x.
# You can tune them later in one place if needed.
MAX_CHAT_INPUT_CHARS = 6000
MAX_CHAT_OUTPUT_CHARS = 12000
MAX_TOOL_OUTPUT_CHARS = 8000


def _to_str(text: Any) -> str:
    if isinstance(text, str):
        return text
    return str(text or "")


def clamp_text(text: Any, limit: int, label: str) -> str:
    """
    Generic helper: clamp text to `limit` characters.

    If clamping happens, appends a transparent note so the user understands
    that truncation occurred, without exposing internal implementation details.
    """
    s = _to_str(text)
    if limit <= 0:
        return s
    if len(s) <= limit:
        return s
    head = s[:limit]
    return head + f"\n\n[{label} truncated — response shortened to avoid overload.]"


def sanitize_chat_input(text: Any) -> str:
    """
    Guardrail for incoming chat text before it is sent to an LLM.

    - Converts non-strings to string
    - Shortens very large inputs
    """
    return clamp_text(text, MAX_CHAT_INPUT_CHARS, "Chat input")


def clamp_chat_output(text: Any) -> str:
    """
    Guardrail for chat model outputs before:

      - saving into chat_storage
      - logging into history
      - returning over the API to the frontend
    """
    return clamp_text(text, MAX_CHAT_OUTPUT_CHARS, "Chat output")


def clamp_tool_output(text: Any) -> str:
    """
    Guardrail for tool results before logging or sending to the chat model.

    This is mainly useful when tools return large JSON structures or logs.
    """
    return clamp_text(text, MAX_TOOL_OUTPUT_CHARS, "Tool output")


def extract_json_object(text: str) -> dict | list | None:
    """
    Extract a JSON object (dict or list) from text that may contain surrounding content.

    Looks for the outermost {} or [] and attempts to parse it as JSON.

    Returns the parsed object if successful and it's a dict or list, None otherwise.
    """
    txt = str(text).strip()
    if ("{" not in txt or "}" not in txt) and ("[" not in txt or "]" not in txt):
        return None
    try:
        # Try dict first
        if "{" in txt and "}" in txt:
            candidate = txt[txt.find("{"): txt.rfind("}") + 1]
            data = json.loads(candidate)
            if isinstance(data, (dict, list)):
                return data
        # Try list
        if "[" in txt and "]" in txt:
            candidate = txt[txt.find("["): txt.rfind("]") + 1]
            data = json.loads(candidate)
            if isinstance(data, (dict, list)):
                return data
    except Exception:
        pass
    return None
