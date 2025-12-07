# tools_runtime.py
"""
Tool runtime for the Personal Local AI OS.

This module provides:
- A registry of local "tools" (small Python functions).
- Functions to list available tools and run them by name.
- A couple of built-in, safe tools for V1:
    - ping: health-check / echo
    - list_models: inspect configured models from config.py

Design goals:
- Completely independent of LLM/chat/code pipelines.
- Safe: tool failures do NOT crash the server; they return {ok: false, ...}.
- JSON-friendly: inputs and outputs are dicts, ready for HTTP.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import (
    AVAILABLE_MODELS,
    CODER_MODEL_NAME,
    REVIEWER_MODEL_NAME,
    JUDGE_MODEL_NAME,
    STUDY_MODEL_NAME,
    CHAT_MODEL_NAME,
    VISION_MODEL_NAME,
)

# Type aliases
ToolFunc = Callable[[Dict[str, Any]], Dict[str, Any]]
ToolSpec = Dict[str, Any]


# =========================
# Internal registry
# =========================

# _TOOLS maps tool name -> {"spec": ToolSpec, "func": ToolFunc}
_TOOLS: Dict[str, Dict[str, Any]] = {}


def register_tool(
    name: str,
    description: str,
    input_schema: Optional[Dict[str, Any]],
    func: ToolFunc,
) -> None:
    """
    Register a tool in the runtime registry.

    name: unique tool name (string identifier).
    description: short human-readable summary.
    input_schema: optional JSON-schema-like dict describing expected params.
                  (For now this is informational; no hard validation.)
    func: callable(params: dict) -> dict (must return JSON-serializable dict).
    """
    if not name or not isinstance(name, str):
        raise ValueError("Tool name must be a non-empty string")
    if not callable(func):
        raise ValueError("func must be callable")

    spec: ToolSpec = {
        "name": name,
        "description": description,
        "input_schema": input_schema or {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }
    _TOOLS[name] = {"spec": spec, "func": func}


def list_tools() -> List[ToolSpec]:
    """
    Return a list of tool specs (without the underlying callables).
    Each item:
      {
        "name": "ping",
        "description": "...",
        "input_schema": {...}
      }
    """
    specs: List[ToolSpec] = []
    for name, entry in sorted(_TOOLS.items(), key=lambda kv: kv[0]):
        specs.append(entry["spec"])
    return specs


def run_tool(name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute a registered tool by name.

    Returns a dict in the form:
      {
        "ok": true/false,
        "result": {...}   # present when ok == true
        "error": "...",   # present when ok == false
        "detail": "..."   # optional extra info on error
      }

    This function NEVER raises for normal tool errors; only programmer bugs
    (e.g. mis-registration) would raise.
    """
    if not isinstance(name, str) or not name:
        return {
            "ok": False,
            "error": "Invalid tool name",
            "detail": f"Expected non-empty string, got: {repr(name)}",
        }

    entry = _TOOLS.get(name)
    if not entry:
        return {
            "ok": False,
            "error": f"Unknown tool '{name}'",
            "detail": "Use /api/tools to list available tools.",
        }

    func: ToolFunc = entry["func"]
    safe_params: Dict[str, Any]
    if params is None:
        safe_params = {}
    elif isinstance(params, dict):
        safe_params = params
    else:
        # Try to coerce non-dict params into a dict wrapper
        safe_params = {"_input": params}

    try:
        raw_result = func(safe_params) or {}
        if not isinstance(raw_result, dict):
            raw_result = {"result": raw_result}
        return {
            "ok": True,
            "result": raw_result,
        }
    except Exception as e:
        # Tool failures must not crash the server.
        return {
            "ok": False,
            "error": "Tool execution failed",
            "detail": str(e),
        }


# =========================
# Built-in tools
# =========================

def _tool_ping(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simple health-check / echo tool.

    Input:
      {
        "message": Optional[str]
      }

    Output:
      {
        "status": "ok",
        "ts": "<ISO timestamp>",
        "message": "<echo or default>"
      }
    """
    message = ""
    if isinstance(params, dict):
        message = str(params.get("message") or "").strip()

    if not message:
        message = "pong"

    ts = datetime.now().isoformat(timespec="seconds")

    return {
        "status": "ok",
        "ts": ts,
        "message": message,
    }


def _tool_list_models(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inspect configured models from config.py.

    Input: {} (ignored)

    Output:
      {
        "available_models": [...],
        "roles": {
          "coder": "...",
          "reviewer": "...",
          "judge": "...",
          "study": "...",
          "chat_default": "...",
          "vision": "..."
        }
      }
    """
    # available_models is the de-duplicated values of AVAILABLE_MODELS.
    available = sorted(set(AVAILABLE_MODELS.values()))

    roles = {
        "coder": CODER_MODEL_NAME,
        "reviewer": REVIEWER_MODEL_NAME,
        "judge": JUDGE_MODEL_NAME,
        "study": STUDY_MODEL_NAME,
        "chat_default": CHAT_MODEL_NAME,
        "vision": VISION_MODEL_NAME,
    }

    return {
        "available_models": available,
        "roles": roles,
    }


def _register_builtin_tools() -> None:
    """
    Register built-in tools at import time.
    """
    register_tool(
        name="ping",
        description="Health-check tool; returns pong + timestamp and optional echo message.",
        input_schema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Optional message to echo back.",
                }
            },
            "required": [],
        },
        func=_tool_ping,
    )

    register_tool(
        name="list_models",
        description="List available Ollama models and which ones are used for each role.",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
        func=_tool_list_models,
    )


# Register built-ins immediately on import
_register_builtin_tools()
