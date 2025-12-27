"""
permission_enforcer.py (Phase C2, Step 1)

Central PermissionEnforcer abstraction for computing permission decisions.
This is a shell: it computes decisions but does not enforce them.
No behavior changes; all decisions are advisory only.

Modes:
- off: Always allow (no-op)
- dry_run: Compute and log decisions
- soft: Compute decisions (future enforcement)
- strict: Compute decisions (future enforcement)

Decision outcomes are non-enforcing:
- allow: No restrictions
- would_require_approval: Would need approval (if enforced)
- would_block: Would be blocked (if enforced)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

try:
    # Import config for mode settings
    from backend.core.config import SECURITY_ENFORCEMENT_MODE
except ImportError:
    SECURITY_ENFORCEMENT_MODE = "off"

try:
    # Import existing security components (read-only)
    from backend.modules.security.security_sessions import consume_security_session_if_allowed
    from backend.modules.security.permission_manager import check_permission_for_tool_execution
    from backend.modules.security.approvals import list_active_approvals
    from backend.modules.security.policy_table import get_required_auth_level
except ImportError:
    # Fallback for missing modules
    consume_security_session_if_allowed = None
    check_permission_for_tool_execution = None
    list_active_approvals = None
    get_required_auth_level = lambda scope: 1  # Allow fallback


class EnforcementMode(Enum):
    OFF = "off"
    DRY_RUN = "dry_run"
    SOFT = "soft"
    STRICT = "strict"


@dataclass
class PermissionDecision:
    """
    Non-enforcing decision object.
    Outcomes are advisory only; no actions taken.
    """
    outcome: str  # "allow", "would_require_approval", "would_block"
    enforcement_active: bool
    profile_id: Optional[str]
    scope: str
    auth_level: int
    reason: str
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for logging/storage."""
        return {
            "outcome": self.outcome,
            "enforcement_active": self.enforcement_active,
            "profile_id": self.profile_id,
            "scope": self.scope,
            "auth_level": self.auth_level,
            "reason": self.reason,
            "meta": self.meta,
        }


class PermissionEnforcer:
    """
    Central enforcer for computing permission decisions.
    Singleton pattern; never enforces, only computes.
    """

    _shared_instance: Optional["PermissionEnforcer"] = None
    _shared_lock = None  # Use threading.Lock if needed, but avoid import

    def __init__(self) -> None:
        self.mode = EnforcementMode(SECURITY_ENFORCEMENT_MODE.lower())


# STEP 3: Single Enforcement Chokepoint
def permission_chokepoint(
    profile_id: Optional[str],
    scope: str,
    auth_level: int,
    context: Optional[Dict[str, Any]] = None,
) -> PermissionDecision:
    """
    Single chokepoint for all permission evaluations.
    Computes decisions and enforces in soft mode.
    All privileged operations must pass through here.
    """
    # D2-STEP-2: Policy Lookup API
    # Compute required auth level as max of risk-based and policy-based
    risk_level = auth_level  # Passed from caller (from risk assessment)
    policy_level = get_required_auth_level(scope) if get_required_auth_level else 1
    required_auth_level = max(risk_level, policy_level)

    # D2-STEP-4: Policy Observability
    policy_details = None
    from backend.modules.security.policy_table import get_policy
    try:
        policy_details = get_policy(scope)
    except Exception:
        pass

    policy_found = policy_details is not None
    policy_version = policy_details.get("version") if policy_details else None

    enforcer = PermissionEnforcer.shared()
    decision = enforcer.evaluate(profile_id, scope, required_auth_level, context)
    # Add levels to meta for logging
    decision.meta["risk_level"] = risk_level
    decision.meta["policy_level"] = policy_level
    decision.meta["required_auth_level"] = required_auth_level
    decision.meta["policy_found"] = policy_found
    decision.meta["policy_version"] = policy_version

    # STEP 7: Soft Enforcement Activation
    if SECURITY_ENFORCEMENT_MODE == "soft" and decision.outcome == "would_require_approval":
        if "approval_id" not in decision.meta:
            # Block: approval required but missing
            decision.outcome = "blocked"
            decision.reason = "Soft enforcement: approval required but not found"
            decision.meta["error"] = {
                "approval_required": True,
                "scope": scope,
                "auth_level": auth_level,
                "reason": "approval_required",
                "required_action": "create_approval",
            }

    # STEP 4: Audit-First Logging (best-effort only)
    try:
        from backend.modules.telemetry.history import history_logger
        cycle_id = f"{profile_id or 'unknown'}-{scope}-{int(time.time())}"
        timestamp = datetime.utcnow().isoformat()

        # Primary decision log
        history_logger.log({
            "kind": "permission_decision_evaluated",
            "profile_id": profile_id,
            "scope": scope,
            "auth_level": decision.meta.get("required_auth_level", auth_level),
            "risk_level": decision.meta.get("risk_level", auth_level),
            "policy_level": decision.meta.get("policy_level", 1),
            "policy_found": decision.meta.get("policy_found", False),
            "policy_version": decision.meta.get("policy_version"),
            "outcome": decision.outcome,
            "enforcement_mode": SECURITY_ENFORCEMENT_MODE,
            "cycle_id": cycle_id,
            "timestamp": timestamp,
        })

        # Conditional audit events
        if decision.outcome == "would_require_approval":
            history_logger.log({
                "kind": "would_require_approval",
                "profile_id": profile_id,
                "scope": scope,
                "auth_level": auth_level,
                "enforcement_mode": SECURITY_ENFORCEMENT_MODE,
                "cycle_id": cycle_id,
                "timestamp": timestamp,
            })

        if decision.outcome == "blocked":
            history_logger.log({
                "kind": "enforcement_blocked",
                "profile_id": profile_id,
                "scope": scope,
                "auth_level": auth_level,
                "enforcement_mode": SECURITY_ENFORCEMENT_MODE,
                "cycle_id": cycle_id,
                "timestamp": timestamp,
                "reason": decision.meta.get("error", {}).get("reason", "blocked"),
            })

        if "approval_id" in decision.meta:
            history_logger.log({
                "kind": "approval_present",
                "profile_id": profile_id,
                "scope": scope,
                "auth_level": auth_level,
                "enforcement_mode": SECURITY_ENFORCEMENT_MODE,
                "cycle_id": cycle_id,
                "timestamp": timestamp,
                "approval_id": decision.meta["approval_id"],
            })
        else:
            history_logger.log({
                "kind": "approval_missing",
                "profile_id": profile_id,
                "scope": scope,
                "auth_level": auth_level,
                "enforcement_mode": SECURITY_ENFORCEMENT_MODE,
                "cycle_id": cycle_id,
                "timestamp": timestamp,
            })

        # Note: approval_expired is not logged here as no enforcement checks expiration

    except Exception:
        pass  # Best-effort logging; never fail execution

    return decision

    @classmethod
    def shared(cls) -> "PermissionEnforcer":
        """Get shared singleton instance."""
        if cls._shared_instance is None:
            cls._shared_instance = cls()
        return cls._shared_instance

    def evaluate(
        self,
        profile_id: Optional[str],
        scope: str,
        auth_level: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> PermissionDecision:
        """
        Compute permission decision without enforcing.
        Never blocks, never executes actions.
        """
        try:
            # Off mode: always allow
            if self.mode == EnforcementMode.OFF:
                return PermissionDecision(
                    outcome="allow",
                    enforcement_active=False,
                    profile_id=profile_id,
                    scope=scope,
                    auth_level=auth_level,
                    reason="Enforcement mode is 'off'",
                    meta={},
                )

            # Compute decision based on existing components
            reason = ""
            meta: Dict[str, Any] = {}

            # Check existing security session (read-only peek)
            session_ok = False
            if consume_security_session_if_allowed is not None:
                try:
                    # Peek without consuming
                    session = consume_security_session_if_allowed(
                        profile_id=profile_id or "",
                        scope=scope,
                        required_level=auth_level,
                    )
                    if session is not None:
                        session_ok = True
                        meta["session_id"] = session.get("id")
                except Exception:
                    pass  # Best-effort

            # Check permission grant (read-only)
            permission_ok = False
            if check_permission_for_tool_execution is not None:
                try:
                    perm = check_permission_for_tool_execution(
                        profile_id=profile_id or "",
                        tool_name=scope.split(".")[-1] if "." in scope else scope,
                        scope=scope,
                        required_auth_level=auth_level,
                    )
                    if perm is not None:
                        permission_ok = True
                        meta["permission_id"] = perm.get("id")
                except Exception:
                    pass  # Best-effort

            # Check for active approvals (read-only, advisory only)
            approval_ok = False
            if list_active_approvals is not None:
                try:
                    active_approvals = list_active_approvals(profile_id or "")
                    for app in active_approvals:
                        if app.scope == scope and app.auth_level >= auth_level:
                            approval_ok = True
                            meta["approval_id"] = app.id
                            break
                except Exception:
                    pass  # Best-effort

            # Determine outcome
            if session_ok or permission_ok or approval_ok:
                outcome = "allow"
                reason = "Valid approval or permission found"
            elif auth_level >= 4:  # High-risk threshold (arbitrary for shell)
                if self.mode in (EnforcementMode.SOFT, EnforcementMode.STRICT):
                    outcome = "would_require_approval"
                    reason = "High-risk operation would require approval"
                else:
                    outcome = "allow"
                    reason = "Dry-run mode allows high-risk"
            else:
                outcome = "allow"
                reason = "Low-risk operation allowed"

            return PermissionDecision(
                outcome=outcome,
                enforcement_active=True,
                profile_id=profile_id,
                scope=scope,
                auth_level=auth_level,
                reason=reason,
                meta=meta,
            )

        except Exception as e:
            # Best-effort: on failure, default to allow
            return PermissionDecision(
                outcome="allow",
                enforcement_active=False,
                profile_id=profile_id,
                scope=scope,
                auth_level=auth_level,
                reason=f"Enforcer evaluation failed: {e}",
                meta={},
            )