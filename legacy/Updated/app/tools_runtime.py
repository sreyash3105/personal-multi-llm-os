"""
Tool runtime for the Personal Local AI OS.

- Central registry for "tools" (Python functions callable via HTTP or LLM).
- Zero dependency on chat/coder/vision pipeline.
- Safe execution: tool failures NEVER crash the server.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.config import (
    AVAILABLE_MODELS,
    CODER_MODEL_NAME,
    REVIEWER_MODEL_NAME,
    JUDGE_MODEL_NAME,
    STUDY_MODEL_NAME,
    CHAT_MODEL_NAME,
    VISION_MODEL_NAME,
)

ToolFunc = Callable[[Dict[str, Any]], Dict[str, Any]]
ToolSpec = Dict[str, Any]


# ============================================================
# Internal registry
# ============================================================
_TOOLS: Dict[str, Dict[str, Any]] = {}


def register_tool(
    name: str,
    description: str,
    input_schema: Optional[Dict[str, Any]],
    func: ToolFunc,
) -> None:
    """
    Register a single tool callable.
    """
    if not name or not isinstance(name, str):
        raise ValueError("Tool name must be a non-empty string.")
    if not callable(func):
        raise ValueError("func must be callable.")

    _TOOLS[name] = {
        "spec": {
            "name": name,
            "description": description,
            "input_schema": input_schema or {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        "func": func,
    }


def list_tools() -> List[ToolSpec]:
    """Return tool metadata without their functions."""
    return [entry["spec"] for _, entry in sorted(_TOOLS.items(), key=lambda kv: kv[0])]


def run_tool(name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute a tool by name.
    Returns a wrapper dict:
      { ok, result?, error?, detail? }
    """
    if not isinstance(name, str) or not name:
        return {"ok": False, "error": "Invalid tool name", "detail": repr(name)}

    entry = _TOOLS.get(name)
    if not entry:
        return {
            "ok": False,
            "error": f"Unknown tool '{name}'",
            "detail": "Use GET /api/tools to list available tools.",
        }

    func: ToolFunc = entry["func"]
    safe_params = params if isinstance(params, dict) else {}

    try:
        raw = func(safe_params) or {}
        if not isinstance(raw, dict):
            raw = {"result": raw}
        return {"ok": True, "result": raw}
    except Exception as e:
        return {"ok": False, "error": "Tool execution failed", "detail": str(e)}


# ============================================================
# Built-in tools
# ============================================================
def _tool_ping(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Small health check / echo tool.
    Input: { "message": "<optional>" }
    """
    msg = ""
    if isinstance(params, dict):
        msg = str(params.get("message") or "").strip()
    if not msg:
        msg = "pong"
    return {
        "status": "ok",
        "ts": datetime.now().isoformat(timespec="seconds"),
        "message": msg,
    }


def _tool_list_models(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return configured Ollama models and role mapping.
    """
    available = sorted(set(AVAILABLE_MODELS.values()))
    return {
        "available_models": available,
        "roles": {
            "coder": CODER_MODEL_NAME,
            "reviewer": REVIEWER_MODEL_NAME,
            "judge": JUDGE_MODEL_NAME,
            "study": STUDY_MODEL_NAME,
            "chat_default": CHAT_MODEL_NAME,
            "vision": VISION_MODEL_NAME,
        },
    }


def _register_builtins():
    register_tool(
        name="ping",
        description="Return pong + timestamp and optional echo message.",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
        },
        func=_tool_ping,
    )

    register_tool(
        name="list_models",
        description="List available models and role assignments.",
        input_schema={"type": "object", "properties": {}},
        func=_tool_list_models,
    )


_register_builtins()
