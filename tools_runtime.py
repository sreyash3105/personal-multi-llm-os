"""
Tools Runtime (V3.0 skeleton)

Central registry + safe execution layer for local tools.

Current status (V3.x with HARDNING BASE Phase 2):
- Registry and execution helpers are defined.
- A single demo "ping" tool is registered.
- The runtime is controlled by feature flags in config.py:
    TOOLS_RUNTIME_ENABLED
    TOOLS_RUNTIME_LOGGING
- Tool execution is:
    - bounded by TOOLS_MAX_RUNTIME_SECONDS (per-call timeout)
    - measured and logged into history as timing entries

V3.4.x — Risk tagging skeleton:
- Each tool execution (and even failed/disabled lookups) is annotated with
  a best-effort risk assessment:
    record["risk"] = {
      "risk_level": 1..6,
      "tags": [...],
      "reasons": "...",
      "kind": "tool",
    }
- This is LOGGING ONLY (no blocking, no auth, no behavior change).

V3.4.x — IO guards integration:
- Tool results can be large; we now clamp ONLY the *logged* representation
  using io_guards.clamp_tool_output before writing to history.
- The value returned to callers (record["result"]) remains unmodified.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from config import TOOLS_RUNTIME_ENABLED, TOOLS_RUNTIME_LOGGING, TOOLS_MAX_RUNTIME_SECONDS
from history import history_logger
from risk import assess_risk
from io_guards import clamp_tool_output  # new: shared output clamp for logging


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

# Global executor for tool execution.
# We keep this modest to avoid tools flooding the system with threads.
_TOOL_EXECUTOR = ThreadPoolExecutor(max_workers=4)


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


def _log_tool_timing(
    name: str,
    duration_s: float,
    status: str,
    error: Optional[str] = None,
) -> None:
    """
    Best-effort timing log for tools into history.

    This does not raise; failure here must never affect tool execution.
    """
    try:
        history_logger.log(
            {
                "kind": "tool_timing",
                "tool": name,
                "duration_s": round(float(duration_s), 3),
                "status": status,
                "error": error,
            }
        )
    except Exception:
        # Logging must be best-effort only.
        pass


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
          "risk": {
             "risk_level": int,
             "tags": List[str],
             "reasons": str,
             "kind": "tool",
          },
        }

    Behavior:
    - If TOOLS_RUNTIME_ENABLED is False:
        returns ok=False with an explanatory error.
    - If the tool is not found:
        returns ok=False with an error.
    - Exceptions inside the tool are caught and reported as error.
    - If the tool takes longer than TOOLS_MAX_RUNTIME_SECONDS:
        returns ok=False with error="tool_timeout", result=None.

    V3.4.x IO guards:
    - The "result" inside the returned record is NOT clamped.
    - For history logging, we create a *separate* truncated representation
      using clamp_tool_output, to keep SQLite entries bounded.
    """
    args = args or {}

    # ----- Risk tagging (logging only, must never raise) -----
    try:
        risk_info = assess_risk(
            "tool",
            {
                "tool": name,
                "args": args,
                "context": context,
            },
        )
    except Exception:
        risk_info = {
            "risk_level": 1,
            "tags": [],
            "reasons": "Risk assessment failed; defaulting to MINOR risk.",
            "kind": "tool",
        }

    if not TOOLS_RUNTIME_ENABLED:
        record = {
            "ok": False,
            "tool": name,
            "result": None,
            "error": "Tools runtime disabled (TOOLS_RUNTIME_ENABLED = False).",
            "meta": {
                "args": args,
                "context_provided": context is not None,
            },
            "risk": risk_info,
        }
        return record

    tool = TOOLS_REGISTRY.get(name)
    if tool is None:
        record = {
            "ok": False,
            "tool": name,
            "result": None,
            "error": f"Tool '{name}' is not registered.",
            "meta": {
                "args": args,
                "context_provided": context is not None,
            },
            "risk": risk_info,
        }
        return record

    result: Any = None
    error: Optional[str] = None
    status: str = "ok"

    start = time.monotonic()
    try:
        future = _TOOL_EXECUTOR.submit(tool.func, args, context)
        result = future.result(timeout=TOOLS_MAX_RUNTIME_SECONDS)
    except FuturesTimeoutError:
        status = "timeout"
        error = f"tool_timeout: exceeded TOOLS_MAX_RUNTIME_SECONDS={TOOLS_MAX_RUNTIME_SECONDS}s"
        result = None
    except Exception as exc:
        status = "error"
        error = f"{type(exc).__name__}: {exc!s}"
        result = None
    finally:
        duration = time.monotonic() - start
        _log_tool_timing(name, duration, status, error)

    # Full record returned to callers (no truncation here).
    record = {
        "ok": error is None,
        "tool": name,
        "result": result if error is None else None,
        "error": error,
        "meta": {
            "args": args,
            "context_provided": context is not None,
        },
        "risk": risk_info,
    }

    # History / dashboard logging (bounded representation)
    if TOOLS_RUNTIME_LOGGING:
        try:
            # Only clamp the *string* representation for history.
            if error is None and result is not None:
                logged_result = clamp_tool_output(result)
            else:
                logged_result = None

            # Build a separate, log-safe copy of the tool record.
            logged_tool_record = dict(record)
            logged_tool_record["result"] = logged_result

            history_logger.log(
                {
                    "mode": "tool_execution",
                    "original_prompt": None,
                    "normalized_prompt": None,
                    "coder_output": None,
                    "reviewer_output": None,
                    "final_output": logged_result,
                    "escalated": False,
                    "escalation_reason": "",
                    "judge": None,
                    "tool_record": logged_tool_record,
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
