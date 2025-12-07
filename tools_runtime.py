"""
Tools Runtime (V3.0 skeleton)

Central registry + safe execution layer for local tools.

Current status (V3.0 step 1):
- Registry and execution helpers are defined.
- A single demo "ping" tool is registered.
- The runtime is controlled by feature flags in config.py:
    TOOLS_RUNTIME_ENABLED
    TOOLS_RUNTIME_LOGGING
- No existing endpoints import or rely on this yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from config import TOOLS_RUNTIME_ENABLED, TOOLS_RUNTIME_LOGGING
from history import history_logger


@dataclass
class Tool:
    """
    Descriptor for a single tool.

    func signature:
        func(args: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any
    """
    name: str
    description: str
    params_schema: Dict[str, Any]
    func: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], Any]


# In-memory registry of all tools, keyed by tool name.
TOOLS_REGISTRY: Dict[str, Tool] = {}


def register_tool(
    name: str,
    description: str,
    params_schema: Optional[Dict[str, Any]],
    func: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], Any],
) -> None:
    """
    Register a tool in the global registry.

    This can be called at import time for static tools, or dynamically
    in future versions when loading tools from plugins.
    """
    if not name or not callable(func):
        raise ValueError("Tool must have a non-empty name and a callable func.")

    schema: Dict[str, Any] = params_schema or {
        "type": "object",
        "properties": {},
        "required": [],
    }

    TOOLS_REGISTRY[name] = Tool(
        name=name,
        description=description or "",
        params_schema=schema,
        func=func,
    )


def execute_tool(
    name: str,
    args: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Safely execute a registered tool.

    Returns a structured dict:

        {
          "ok": bool,
          "tool": str,
          "result": Any | None,
          "error": str | None,
          "meta": {
             "args": Dict[str, Any],
             "context_provided": bool,
          },
        }

    Behavior:
    - If TOOLS_RUNTIME_ENABLED is False:
        returns ok=False with an explanatory error.
    - If the tool is not found:
        returns ok=False with an error.
    - Exceptions inside the tool are caught and reported as error.
    """
    args = args or {}

    if not TOOLS_RUNTIME_ENABLED:
        return {
            "ok": False,
            "tool": name,
            "result": None,
            "error": "Tools runtime disabled (TOOLS_RUNTIME_ENABLED = False).",
            "meta": {
                "args": args,
                "context_provided": context is not None,
            },
        }

    tool = TOOLS_REGISTRY.get(name)
    if tool is None:
        return {
            "ok": False,
            "tool": name,
            "result": None,
            "error": f"Tool '{name}' is not registered.",
            "meta": {
                "args": args,
                "context_provided": context is not None,
            },
        }

    result: Any = None
    error: Optional[str] = None

    try:
        result = tool.func(args, context)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc!s}"

    record = {
        "ok": error is None,
        "tool": name,
        "result": result if error is None else None,
        "error": error,
        "meta": {
            "args": args,
            "context_provided": context is not None,
        },
    }

    if TOOLS_RUNTIME_LOGGING:
        try:
            history_logger.log(
                {
                    "mode": "tool_execution",
                    "original_prompt": None,
                    "normalized_prompt": None,
                    "coder_output": None,
                    "reviewer_output": None,
                    "final_output": result if error is None else None,
                    "escalated": False,
                    "escalation_reason": "",
                    "judge": None,
                    "tool_record": record,
                }
            )
        except Exception:
            # Logging must never break tool execution.
            pass

    return record


# =========================
# Built-in demo tools
# =========================

def _ping_tool(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Simple connectivity / sanity-check tool.

    Args:
      - message: optional string to echo back.

    Returns:
      {"message": <string>, "context_seen": bool}
    """
    message = args.get("message") if isinstance(args, dict) else None
    if not message:
        message = "pong"
    return {
        "message": str(message),
        "context_seen": context is not None,
    }


# Register built-in demo tools at import time.
register_tool(
    name="ping",
    description="Simple connectivity check tool that echoes a message.",
    params_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Optional message to echo back."}
        },
        "required": [],
    },
    func=_ping_tool,
)
