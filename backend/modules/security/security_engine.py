"""
security_engine.py

V3.5 — Security System (Phase 1)
--------------------------------
Centralized engine to map risk information → security authorization level (1–6).

This module is deliberately self-contained and non-invasive:
- No side effects on import.
- No required DB or FastAPI dependencies.
- No changes to sacred modules.
- Safe to import from anywhere (tools_runtime, endpoints, etc.) when you’re ready.

Concepts
--------
- risk_score: float, typically from risk.py (0.0–10.0 or similar).
- operation_type: high-level tag for what is happening (e.g. "tool_call", "file_write").
- tool_name: optional, for tool-specific overrides (e.g. "shell", "delete_file").
- context_tags: optional set/list of flags (e.g. {"network", "filesystem", "privacy_sensitive"}).

Auth levels (1–6)
-----------------
1 — Allow silently (safe)
2 — Allow and log (low risk, but track)
3 — Require simple confirmation (YES/NO) for medium risk
4 — Require confirmation + elevated logging (sensitive medium/high)
5 — Require strong verification (password/phrase) for high risk
6 — Block or require admin override (critical)

Later integration
-----------------
- /api/security/auth can use this engine to decide what kind of challenge to create.
- UI popups use auth_level to pick UX: simple prompt vs password phrase.
- Dashboard can aggregate SecurityDecision events.

This file is the core policy brain; it does NOT perform any IO itself.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, Iterable, List, Optional, Set

try:
    # Optional: use config if available, but fall back safely if not.
    import backend.core.config as _config  # type: ignore
except Exception:  # pragma: no cover - defensive
    _config = None  # type: ignore


class SecurityAuthLevel(IntEnum):
    """
    Security authorization levels.

    These levels are intentionally generic so they can be reused for:
    - Tool calls
    - System actions
    - File operations
    - Network operations
    """

    ALLOW = 1
    LOG_ONLY = 2
    CONFIRM = 3
    CONFIRM_SENSITIVE = 4
    STRONG_VERIFY = 5
    BLOCK = 6


@dataclass
class SecurityDecision:
    """
    Result returned by SecurityEngine for a given operation.

    Fields:
        auth_level: the required authorization level (1–6).
        reason: human-readable explanation for logs / UI / dashboard.
        risk_score: numeric risk score used for the decision.
        tags: optional tags about the decision (e.g. {"medium_risk", "filesystem"}).
        policy_name: which policy rule or profile produced this decision.
        meta: extra structured data for logging or downstream systems.
    """

    auth_level: SecurityAuthLevel
    reason: str
    risk_score: float
    tags: Set[str] = field(default_factory=set)
    policy_name: str = "default"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityEngineConfig:
    """
    Configuration for SecurityEngine.

    risk_thresholds: numeric boundaries that map risk_score → auth levels.
        Example structure (all values inclusive on lower bound):
            {
                "allow_max": 1.9,
                "log_only_max": 3.9,
                "confirm_max": 5.9,
                "confirm_sensitive_max": 7.9,
                "strong_verify_max": 8.9,
                # >= strong_verify_max → BLOCK
            }

    tool_overrides:
        Optional per-tool rules that can force minimum auth levels or add tags.
        Example:
            {
                "shell": {"min_level": 5, "tags": ["system", "shell"]},
                "delete_file": {"min_level": 4, "tags": ["filesystem", "destructive"]},
            }

    operation_overrides:
        Similar to tool_overrides, but keyed by operation_type.
        Example keys: "tool_call", "file_write", "network_request".
    """

    risk_thresholds: Dict[str, float]
    tool_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    operation_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def _default_risk_thresholds() -> Dict[str, float]:
    """
    Conservative defaults that do not aggressively block operations,
    but provide useful gradation for UI challenges.

    You can override these via config.SECURITY_RISK_THRESHOLDS if desired.
    """
    return {
        "allow_max": 1.9,
        "log_only_max": 3.9,
        "confirm_max": 5.9,
        "confirm_sensitive_max": 7.9,
        "strong_verify_max": 8.9,
        # >= strong_verify_max → BLOCK
    }


def _load_engine_config_from_config_module() -> SecurityEngineConfig:
    """
    Attempt to load configuration from config.py without requiring any changes.

    Expected optional attributes on config (all optional):
        SECURITY_RISK_THRESHOLDS: dict with same shape as _default_risk_thresholds()
        SECURITY_TOOL_OVERRIDES: dict for tool-specific policies
        SECURITY_OPERATION_OVERRIDES: dict for operation-specific policies

    If any are missing, safe defaults are used.
    """
    thresholds = _default_risk_thresholds()
    tool_overrides: Dict[str, Dict[str, Any]] = {}
    operation_overrides: Dict[str, Dict[str, Any]] = {}

    if _config is not None:
        try:
            custom = getattr(_config, "SECURITY_RISK_THRESHOLDS", None)
            if isinstance(custom, dict):
                thresholds.update(custom)
        except Exception:
            # Fail-safe: keep defaults
            pass

        try:
            to = getattr(_config, "SECURITY_TOOL_OVERRIDES", None)
            if isinstance(to, dict):
                tool_overrides.update(to)
        except Exception:
            pass

        try:
            oo = getattr(_config, "SECURITY_OPERATION_OVERRIDES", None)
            if isinstance(oo, dict):
                operation_overrides.update(oo)
        except Exception:
            pass

    return SecurityEngineConfig(
        risk_thresholds=thresholds,
        tool_overrides=tool_overrides,
        operation_overrides=operation_overrides,
    )


class SecurityEngine:
    """
    Core policy engine for V3.5 security.

    Usage pattern (later, from tools_runtime or FastAPI endpoints):
        engine = SecurityEngine.shared()
        decision = engine.evaluate(
            risk_score=risk,
            operation_type="tool_call",
            tool_name="delete_file",
            context_tags={"filesystem", "destructive"},
        )
        # Use decision.auth_level to decide if you need:
        # - No auth
        # - YES/NO popup
        # - Password / phrase
        # - Block

    This class is intentionally lightweight and stateless beyond its config.
    """

    _shared_instance: Optional["SecurityEngine"] = None
    _shared_lock = threading.Lock()

    def __init__(self, config: Optional[SecurityEngineConfig] = None) -> None:
        self.config = config or _load_engine_config_from_config_module()

    # ---------- Shared singleton helper ----------

    @classmethod
    def shared(cls) -> "SecurityEngine":
        """
        Lazily initialized shared engine.

        Safe to call from anywhere. Does not perform IO.
        """
        with cls._shared_lock:
            if cls._shared_instance is None:
                cls._shared_instance = cls()
            return cls._shared_instance

    # ---------- Public API ----------

    def evaluate(
        self,
        risk_score: float,
        operation_type: str,
        tool_name: Optional[str] = None,
        context_tags: Optional[Iterable[str]] = None,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> SecurityDecision:
        """
        Compute a SecurityDecision for the given operation.

        Parameters:
            risk_score: numeric risk score (e.g., from risk.py).
            operation_type: high-level category of the operation.
            tool_name: optional tool identifier, if applicable.
            context_tags: optional iterable of tags describing context.
            extra_meta: optional additional structured info to attach.

        Returns:
            SecurityDecision describing auth level & reasoning.
        """
        ctx_tags: Set[str] = set(context_tags or [])
        meta: Dict[str, Any] = dict(extra_meta or {})

        # Base auth level purely from risk_score.
        base_level = self._auth_level_from_risk(risk_score)
        tags = {f"risk_{base_level.name.lower()}"}
        policy_name = "base_risk_policy"
        reason_parts: List[str] = [
            f"risk_score={risk_score:.2f}",
            f"operation_type={operation_type}",
        ]

        # Apply operation_type overrides (if any).
        base_level, policy_name, op_tags = self._apply_operation_overrides(
            base_level, operation_type
        )
        tags.update(op_tags)

        # Apply tool-specific overrides (if any).
        if tool_name:
            base_level, policy_name, tool_tags = self._apply_tool_overrides(
                base_level, tool_name
            )
            tags.update(tool_tags)
            meta["tool_name"] = tool_name

        tags.update(ctx_tags)
        meta["operation_type"] = operation_type

        reason = "; ".join(reason_parts + [f"auth_level={base_level.name}"])

        return SecurityDecision(
            auth_level=base_level,
            reason=reason,
            risk_score=risk_score,
            tags=tags,
            policy_name=policy_name,
            meta=meta,
        )

    # ---------- Internal helpers ----------

    def _auth_level_from_risk(self, risk_score: float) -> SecurityAuthLevel:
        """
        Map raw risk_score → baseline SecurityAuthLevel using configured thresholds.
        """
        t = self.config.risk_thresholds

        # Use .get with defaults to be robust to missing keys.
        allow_max = float(t.get("allow_max", 1.9))
        log_only_max = float(t.get("log_only_max", 3.9))
        confirm_max = float(t.get("confirm_max", 5.9))
        confirm_sensitive_max = float(t.get("confirm_sensitive_max", 7.9))
        strong_verify_max = float(t.get("strong_verify_max", 8.9))

        if risk_score <= allow_max:
            return SecurityAuthLevel.ALLOW
        if risk_score <= log_only_max:
            return SecurityAuthLevel.LOG_ONLY
        if risk_score <= confirm_max:
            return SecurityAuthLevel.CONFIRM
        if risk_score <= confirm_sensitive_max:
            return SecurityAuthLevel.CONFIRM_SENSITIVE
        if risk_score <= strong_verify_max:
            return SecurityAuthLevel.STRONG_VERIFY
        return SecurityAuthLevel.BLOCK

    def _apply_operation_overrides(
        self,
        base_level: SecurityAuthLevel,
        operation_type: str,
    ) -> tuple[SecurityAuthLevel, str, Set[str]]:
        """
        Apply operation_type-specific minimum auth levels and tags.

        Example config entry:
            SECURITY_OPERATION_OVERRIDES = {
                "file_write": {"min_level": 3, "tags": ["filesystem"]},
                "network_request": {"min_level": 2, "tags": ["network"]},
            }
        """
        overrides = self.config.operation_overrides.get(operation_type)
        if not overrides:
            return base_level, "base_risk_policy", set()

        min_level_value = overrides.get("min_level")
        tags = set(overrides.get("tags", []))

        policy_name = overrides.get("policy_name", f"operation:{operation_type}")

        if isinstance(min_level_value, int):
            try:
                min_level = SecurityAuthLevel(min_level_value)
            except ValueError:
                min_level = base_level
        else:
            min_level = base_level

        final_level = max(base_level, min_level)
        return final_level, policy_name, tags

    def _apply_tool_overrides(
        self,
        base_level: SecurityAuthLevel,
        tool_name: str,
    ) -> tuple[SecurityAuthLevel, str, Set[str]]:
        """
        Apply tool-specific minimum auth levels and tags.

        Example config entry:
            SECURITY_TOOL_OVERRIDES = {
                "shell": {"min_level": 5, "tags": ["system", "shell"]},
                "delete_file": {"min_level": 4, "tags": ["filesystem", "destructive"]},
            }
        """
        overrides = self.config.tool_overrides.get(tool_name)
        if not overrides:
            return base_level, "base_risk_policy", set()

        min_level_value = overrides.get("min_level")
        tags = set(overrides.get("tags", []))
        policy_name = overrides.get("policy_name", f"tool:{tool_name}")

        if isinstance(min_level_value, int):
            try:
                min_level = SecurityAuthLevel(min_level_value)
            except ValueError:
                min_level = base_level
        else:
            min_level = base_level

        final_level = max(base_level, min_level)
        return final_level, policy_name, tags
# ==========================================
# SECURITY ENFORCEMENT SIGNALS (V3.6)
# ==========================================
# Non-blocking: nothing is stopped, no raise, no deny.
# Only logs + returns event payload so dashboard and chat UI can react.

from typing import Optional
from backend.modules.security.security_sessions import get_best_session_for_scope


def security_evaluate_operation(
    *,
    profile_id: str,
    scope: str,
    required_level: int,
) -> dict:
    """
    Called by tools_runtime or pipeline to detect whether an operation
    should trigger a security approval flow on the UI side.
    Always returns a dict; NEVER throws.
    """

    # wildcard approval covers everything (tool:*)
    wildcard = get_best_session_for_scope(
        profile_id=profile_id,
        scope="tool:*",
        required_level=required_level,
    )
    if wildcard is not None:
        return {
            "approval_required": False,
            "approved_scope": "tool:*",
            "mode": "wildcard",
        }

    # scope-specific approval exists?
    sess = get_best_session_for_scope(
        profile_id=profile_id,
        scope=scope,
        required_level=required_level,
    )
    if sess is not None:
        return {
            "approval_required": False,
            "approved_scope": scope,
            "mode": "session",
            "session_id": sess.get("id"),
            "expires_at": sess.get("expires_at"),
        }

    # NO approval session present — UI should ask user
    return {
        "approval_required": True,
        "scope": scope,
        "required_level": required_level,
    }
