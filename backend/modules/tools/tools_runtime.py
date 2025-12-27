from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
import logging
import time
from typing import Any, Callable, Dict, Optional, List, Set

logger = logging.getLogger(__name__)

from backend.core.config import (
    TOOLS_RUNTIME_ENABLED,
    TOOLS_RUNTIME_LOGGING,
    TOOLS_MAX_RUNTIME_SECONDS,
    SECURITY_ENFORCEMENT_MODE,
    SECURITY_MIN_ENFORCED_LEVEL,
    PERMISSION_SYSTEM_ENABLED,
)
from backend.modules.common.io_guards import clamp_tool_output  # shared output clamp for logging
# Phase C2: Permission Enforcer Shell (observability only)
from backend.modules.security.permission_enforcer import permission_chokepoint
from backend.modules.security.permission_scopes import build_tool_scope
from backend.modules.security.security_engine import SecurityEngine, SecurityAuthLevel
from backend.modules.security.security_sessions import consume_security_session_if_allowed
from backend.modules.telemetry.history import history_logger
from backend.modules.telemetry.risk import assess_risk

# Phase C: Permission system hooks (feature-flagged OFF)
if PERMISSION_SYSTEM_ENABLED:
    from backend.modules.security.permission_manager import check_permission_for_tool_execution
else:
    check_permission_for_tool_execution = None

# 🟢 NEW IMPORTS: Import tool registries from specific tool files
# Note: file_tools.py must be importable (and implicitly registers file/kb tools)
from backend.modules.tools.file_tools import TOOL_REGISTRY as FILE_TOOL_REGISTRY
# Assuming pc_control_tools.py is the new file for PC automation (mouse/keyboard)
# You need to ensure this file exists with the TOOL_REGISTRY_PC_CONTROL dict defined.
try:
    from backend.modules.tools.pc_control_tools import TOOL_REGISTRY_PC_CONTROL
except ImportError:
    TOOL_REGISTRY_PC_CONTROL = {}
# ----------------------------------------------------------------------------------


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


def _build_security_context_tags(
    risk_info: Dict[str, Any],
    context: Optional[Dict[str, Any]],
) -> List[str]:
    """
    Build a small tag set for SecurityEngine from risk + context.

    This is deliberately conservative and must never raise.
    """
    tags: Set[str] = set()

    # From risk_info
    try:
        r_tags = risk_info.get("tags") or []
        if isinstance(r_tags, list):
            for t in r_tags:
                if t is None:
                    continue
                tags.add(str(t))
    except Exception:
        # Best-effort only
        pass

    # From context (source, profile/chat presence)
    if isinstance(context, dict):
        src = context.get("source")
        if src:
            tags.add(f"source:{src}")

        if context.get("profile_id"):
            tags.add("has_profile")

        if context.get("chat_id"):
            tags.add("has_chat")

    return sorted(tags)


def _compute_security_decision(
    tool_name: str,
    risk_info: Dict[str, Any],
    context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Call SecurityEngine to obtain a non-blocking authorization decision.

    This must never raise; on failure we fall back to a minimal "ALLOW"
    decision so that tool behavior is unaffected.
    """
    try:
        raw_risk = risk_info.get("risk_level", 1)
        try:
            risk_score = float(raw_risk)
        except Exception:
            risk_score = 1.0

        engine = SecurityEngine.shared()
        ctx_tags = _build_security_context_tags(risk_info, context)

        decision = engine.evaluate(
            risk_score=risk_score,
            operation_type="tool_call",
            tool_name=tool_name,
            context_tags=ctx_tags,
            extra_meta={
                "risk_level_from_risk_module": raw_risk,
            },
        )

        return {
            "auth_level": int(decision.auth_level),
            "auth_label": decision.auth_level.name,
            "reason": decision.reason,
            "risk_score": float(decision.risk_score),
            "tags": sorted(decision.tags),
            "policy_name": decision.policy_name,
            "meta": decision.meta,
        }
    except Exception as e:
        # Security failure: log and BLOCK to fail closed
        logger.error(f"SecurityEngine evaluation failed: {e}")
        return {
            "auth_level": int(SecurityAuthLevel.BLOCK),
            "auth_label": SecurityAuthLevel.BLOCK.name,
            "reason": f"SecurityEngine evaluation failed: {e}; defaulting to BLOCK.",
            "risk_score": float(risk_info.get("risk_level") or 10.0),  # High risk
            "tags": ["security_engine_error"],
            "policy_name": "security_engine_fallback",
            "meta": {},
        }


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
          "security": {
             "auth_level": int,
             "auth_label": str,
             "reason": str,
             "risk_score": float,
             "tags": List[str],
             "policy_name": str,
             "meta": Dict[str, Any],
          },
          "requires_approval": bool,
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

    V3.5 security wiring:
    - SecurityEngine is consulted for every call to compute a non-blocking
      auth decision stored under record["security"].

    V3.7 security enforcement (config-gated):
    - When SECURITY_ENFORCEMENT_MODE is "soft" or "strict" and
      auth_level >= SECURITY_MIN_ENFORCED_LEVEL:
        * "soft": require a prior approval session, otherwise return
          error="security_approval_required" and requires_approval=True.
        * "strict": return error="security_blocked" with no session bypass.
    """
    name = (name or "").strip()
    if not name:
        return {
            "ok": False,
            "tool": name,
            "result": None,
            "error": "Tool name cannot be empty",
            "meta": {"args": args or {}, "context_provided": context is not None},
            "risk": {"risk_level": 1, "tags": [], "reasons": "Invalid tool name"},
            "security": {"auth_level": 1, "auth_label": "ALLOW", "reason": "Invalid tool name", "risk_score": 1.0, "tags": [], "policy_name": "invalid_tool", "meta": {}},
            "requires_approval": False,
        }

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

    # ----- Security decision (telemetry + optional enforcement) -----
    security_info = _compute_security_decision(name, risk_info, context)

    # Default: no approval required (overridden below if enforced)
    requires_approval = False

    # Fast path: runtime disabled → short-circuit (no enforcement)
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
            "security": security_info,
            "requires_approval": requires_approval,
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
            "security": security_info,
            "requires_approval": requires_approval,
        }
        return record

    # ----- Phase C: Permission system hooks (feature-flagged OFF) -----
    permission_info = None
    if PERMISSION_SYSTEM_ENABLED and check_permission_for_tool_execution:
        try:
            # Use the auth_level from security_info as required_auth_level
            required_auth_level = int(security_info.get("auth_level", 1))
            permission_info = check_permission_for_tool_execution(
                profile_id="",  # profile_id defined later, use empty for now
                tool_name=name,
                scope=f"tool:{name}",
                required_auth_level=required_auth_level,
            )
            # Future: use permission_info for enforcement
        except Exception as e:
            logger.warning(f"Permission check failed: {e}")

    # ----- Optional enforcement (config-controlled) -----
    try:
        auth_level = int(security_info.get("auth_level", 1))
    except Exception:
        auth_level = 1

    profile_id = ""
    if isinstance(context, dict):
        profile_id = (context.get("profile_id") or "").strip()

    # Phase C2: Permission Enforcer Shell (observability only)
    permission_evaluation = None
    decision = None
    try:
        decision = permission_chokepoint(
            profile_id=profile_id,
            scope=build_tool_scope(name),
            auth_level=auth_level,
            context=context,
        )
        permission_evaluation = {
            "mode": SECURITY_ENFORCEMENT_MODE,
            "decision": decision.to_dict(),
        }
    except Exception:
        pass  # Best-effort, ignore failures

    # STEP 7: Soft Enforcement Check
    if decision and decision.outcome == "blocked":
        error_info = decision.meta.get("error", {})
        record = {
            "ok": False,
            "tool": name,
            "result": None,
            "error": error_info.get("reason", "approval_required"),
            "approval_required": True,
            "scope": error_info.get("scope"),
            "auth_level": error_info.get("auth_level"),
            "required_action": error_info.get("required_action"),
            "meta": {
                "args": args,
                "context_provided": context is not None,
            },
            "risk": risk_info,
            "security": security_info,
            "requires_approval": True,
            "permission_evaluation": permission_evaluation,
        }
        # Log blocked execution
        if TOOLS_RUNTIME_LOGGING:
            try:
                logged_tool_record = dict(record)
                history_logger.log(
                    {
                        "mode": "tool_execution",
                        "original_prompt": None,
                        "normalized_prompt": None,
                        "coder_output": None,
                        "reviewer_output": None,
                        "final_output": None,
                        "escalated": False,
                        "escalation_reason": "",
                        "judge": None,
                        "tool_record": logged_tool_record,
                    }
                )
            except Exception:
                pass
        return record

    if SECURITY_ENFORCEMENT_MODE in ("soft", "strict") and auth_level >= SECURITY_MIN_ENFORCED_LEVEL:

        session_ok = False
        if SECURITY_ENFORCEMENT_MODE == "soft" and profile_id:
            try:
                # Scope: specific tool; future: support "tool:*"
                session_ok = consume_security_session_if_allowed(
                    profile_id=profile_id,
                    scope=build_tool_scope(name),
                    required_level=auth_level,
                )
            except Exception:
                session_ok = False

        # Decide whether to block
        if SECURITY_ENFORCEMENT_MODE == "strict" or (SECURITY_ENFORCEMENT_MODE == "soft" and not session_ok):
            error_msg = "security_approval_required" if SECURITY_ENFORCEMENT_MODE == "soft" else "security_blocked"
            requires_approval = (SECURITY_ENFORCEMENT_MODE == "soft")

            record = {
                "ok": False,
                "tool": name,
                "result": None,
                "error": error_msg,
                "meta": {
                    "args": args,
                    "context_provided": context is not None,
                },
                "risk": risk_info,
                "security": security_info,
                "requires_approval": requires_approval,
            }

            # Log this as a tool_execution with no result
            if TOOLS_RUNTIME_LOGGING:
                try:
                    logged_tool_record = dict(record)
                    history_logger.log(
                        {
                            "mode": "tool_execution",
                            "original_prompt": None,
                            "normalized_prompt": None,
                            "coder_output": None,
                            "reviewer_output": None,
                            "final_output": None,
                            "escalated": False,
                            "escalation_reason": "",
                            "judge": None,
                            "tool_record": logged_tool_record,
                        }
                    )
                except Exception:
                    # Logging must never break enforcement.
                    pass

            return record

    # Phase C2: Permission Enforcer Shell (observability only)
    permission_evaluation = None
    try:
        enforcer = PermissionEnforcer.shared()
        decision = enforcer.evaluate(
            profile_id=profile_id,
            scope=f"tool:{name}",
            auth_level=auth_level,
            context=context,
        )
        permission_evaluation = {
            "mode": SECURITY_ENFORCEMENT_MODE,
            "decision": decision.to_dict(),
        }
    except Exception:
        pass  # Best-effort, ignore failures

    # ----- Actual tool execution (if not blocked) -----
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
        "security": security_info,
        "requires_approval": requires_approval,
        "permission_evaluation": permission_evaluation,
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

# 🟢 NEW: Centralized tool registration function
def _auto_register_all_tools():
    """
    Registers all tools from internal modules and built-ins.
    """
    # 1. Register built-in tool(s)
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

    # Helper to get a rudimentary schema/description from the function name
    def _get_default_metadata(name):
        return {
            "description": f"Function from the {name.split('_')[0]} module.",
            "params_schema": {
                "type": "object",
                "properties": {"args": {"type": "object"}},
                "required": [],
            }
        }

    # 2. Register tools from file_tools.py (KB/File operations)
    for name, func in FILE_TOOL_REGISTRY.items():
        meta = _get_default_metadata(name)
        register_tool(name=name, **meta, func=func)

    # 3. Register tools from pc_control_tools.py (PC Control)
    for name, func in TOOL_REGISTRY_PC_CONTROL.items():
        meta = _get_default_metadata(name)
        register_tool(name=name, **meta, func=func)
    
# Call this function once at module import time to populate the registry.
_auto_register_all_tools()
# -------------------------------------------------------------------------

# ==========================================
# SECURITY ENFORCEMENT EXTENSION (V3.6)
# ==========================================
#
# This layer runs BEFORE executing a tool.
...
# All remaining security enforcement functions (security_gate_for_tool, etc.)
# are unchanged from the original source file.
# ------------------------------------------------------------------------


# 🟢 The security enforcement functions from the original source are assumed to be 
# included here after the changes above.

from backend.modules.security.security_sessions import (
    sec_check_or_consume,
    sec_has_tool_wildcard,
)


def security_gate_for_tool(
    *,
    profile_id: str,
    tool_name: str,
    required_level: int,
    consume: bool = True,
) -> dict:
    """
    Decide whether a tool is allowed to run.
    Returns:
        { "ok": True }                        → allowed
        { "ok": False, "reason": "..."}       → block
    """

    scope = build_tool_scope(tool_name)

    # wildcard approval covers all tools (approved once for the profile)
    if sec_has_tool_wildcard(profile_id=profile_id, required_level=required_level):
        return {"ok": True, "scope": "tool:*", "mode": "wildcard"}

    # scope-specific session (either peek or consume)
    sess = sec_check_or_consume(
        profile_id=profile_id,
        scope=scope,
        required_level=required_level,
        consume=consume,
    )

    if sess is not None:
        return {
            "ok": True,
            "scope": scope,
            "mode": "session",
            "session_id": sess.get("id"),
            "remaining_uses": max(0, sess.get("max_uses", 1) - sess.get("used_count", 0)),
            "expires_at": sess.get("expires_at"),
        }

    # No session = block (soft mode)
    return {
        "ok": False,
        "reason": "security_approval_required",
        "scope": scope,
        "required_level": required_level,
    }