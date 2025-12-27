from __future__ import annotations

from datetime import datetime
from typing import Optional

from backend.modules.security.approvals import create_approval, list_active_approvals, revoke_approval, Approval
from backend.modules.security.policy_table import get_policy
from backend.modules.telemetry.history import history_logger


def create_approval_request(
    profile_id: str,
    scope: str,
    auth_level: int,
    issued_by: str,
    ttl_seconds: int = 3600,
    max_uses: int = 1
) -> dict:
    if not profile_id or not profile_id.strip():
        raise ValueError("profile_id must be non-empty string")
    if not scope or not scope.strip():
        raise ValueError("scope must be non-empty string")
    if not issued_by or not issued_by.strip():
        raise ValueError("issued_by must be non-empty string")
    if not scope.startswith(("file.", "tool.", "system.")):
        raise ValueError("Scope must be canonical (start with file., tool., or system.)")

    approval = create_approval(
        profile_id=profile_id,
        scope=scope,
        auth_level=auth_level,
        issued_by=issued_by,
        ttl_seconds=ttl_seconds,
        max_uses=max_uses,
    )

    try:
        history_logger.log({
            "kind": "approval_created",
            "approval_id": approval.id,
            "profile_id": approval.profile_id,
            "scope": approval.scope,
            "auth_level": approval.auth_level,
            "issued_by": approval.issued_by,
            "ttl_seconds": ttl_seconds,
            "max_uses": max_uses,
        })
    except Exception:
        pass

    return {"status": "created", "approval": approval.to_dict()}


def list_active_approvals_request(profile_id: str) -> dict:
    if not profile_id or not profile_id.strip():
        raise ValueError("profile_id must be non-empty string")

    approvals = list_active_approvals(profile_id)
    now = datetime.utcnow()

    result = []
    for a in approvals:
        time_remaining = max(0, (a.expires_at - now).total_seconds())
        uses_remaining = a.max_uses - a.used_count
        result.append({
            "id": a.id,
            "scope": a.scope,
            "auth_level": a.auth_level,
            "issued_by": a.issued_by,
            "issued_at": a.issued_at.isoformat(),
            "expires_at": a.expires_at.isoformat(),
            "max_uses": a.max_uses,
            "used_count": a.used_count,
            "uses_remaining": uses_remaining,
            "time_remaining_seconds": time_remaining,
        })

    return {"approvals": result}


def revoke_approval_request(approval_id: int, profile_id: str) -> dict:
    success = revoke_approval(approval_id, profile_id)
    if not success:
        raise ValueError("Approval not found or profile mismatch")

    try:
        history_logger.log({
            "kind": "approval_revoked",
            "approval_id": approval_id,
            "profile_id": profile_id,
        })
    except Exception:
        pass

    return {"status": "revoked", "approval_id": approval_id}


def get_policy_request(scope: str) -> dict:
    policy = get_policy(scope)
    if policy is None:
        raise ValueError(f"Policy not found for scope: {scope}")
    return {"policy": policy}
