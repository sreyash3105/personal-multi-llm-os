"""
MEK-2: Authority Primitives

Principal, Grant, Revocation - time-bound authority.
No intelligence. No autonomy. Authority is data + enforcement.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import time
import threading
import uuid

# Shared lock for atomic use decrements
_grant_use_lock = threading.Lock()


class RevocationReason(Enum):
    """Reason for revocation."""
    EXPLICIT_REVOCATION = "explicit_revocation"
    SECURITY_VIOLATION = "security_violation"
    PRINCIPAL_COMPROMISED = "principal_compromised"
    GRANT_LEAK = "grant_leak"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"


# PRIMITIVE 1: PRINCIPAL (EXPLICIT ACTOR)
@dataclass(frozen=True)
class Principal:
    """
    Explicit actor identifier.

    - principal_id (opaque string)
    - No hierarchy
    - No inference
    - Missing principal -> refusal
    """

    principal_id: str

    def __post_init__(self):
        if not self.principal_id:
            raise ValueError("Principal: principal_id is required")
        if len(self.principal_id) > 256:
            raise ValueError(
                f"Principal: principal_id too long (max 256 chars): {len(self.principal_id)}"
            )


def create_principal(principal_id: str) -> Principal:
    """Create a principal."""
    return Principal(principal_id=principal_id)


# PRIMITIVE 2: GRANT (TIME-BOUND AUTHORITY)
@dataclass(frozen=True)
class Grant:
    """
    Time-bound authority grant.

    Immutable once issued.
    - Cannot be edited
    - Fabrication outside kernel -> impossible
    """

    grant_id: str
    principal_id: str
    capability_name: str
    scope: str
    issued_at: float  # Monotonic time
    expires_at: float  # Monotonic time
    max_uses: Optional[int] = None
    revocable: bool = True

    def __post_init__(self):
        # Validate fields
        if not self.grant_id:
            raise ValueError("Grant: grant_id is required")
        if not self.principal_id:
            raise ValueError("Grant: principal_id is required")
        if not self.capability_name:
            raise ValueError("Grant: capability_name is required")
        if not self.scope:
            raise ValueError("Grant: scope is required")
        if self.issued_at >= self.expires_at:
            raise ValueError(
                f"Grant: issued_at ({self.issued_at}) must be before expires_at ({self.expires_at})"
            )
        if self.max_uses is not None and self.max_uses <= 0:
            raise ValueError(f"Grant: max_uses must be > 0, got {self.max_uses}")

    def is_expired(self, current_time: float) -> bool:
        """Check if grant has expired."""
        return current_time >= self.expires_at

    def has_remaining_uses(self, remaining_uses: int) -> bool:
        """Check if grant has remaining uses."""
        if self.max_uses is None:
            return True
        return remaining_uses > 0


def decrement_grant_use(remaining_uses: int) -> int:
    """
    Atomically decrement grant uses.

    MEK-2: Atomicity
    - Must be thread-safe
    - Must not go negative
    """
    if remaining_uses > 0:
        return remaining_uses - 1
    return remaining_uses


# PRIMITIVE 3: REVOCATION EVENT (TERMINAL)
@dataclass(frozen=True)
class RevocationEvent:
    """
    Terminal revocation event.

    - Targets grant_id
    - Irreversible
    - Overrides everything
    - Revocation always wins
    """

    grant_id: str
    revoked_by_principal: str
    reason: RevocationReason
    revoked_at: float  # Monotonic time

    def __post_init__(self):
        if not self.grant_id:
            raise ValueError("RevocationEvent: grant_id is required")
        if not self.revoked_by_principal:
            raise ValueError("RevocationEvent: revoked_by_principal is required")
        if self.revoked_at <= 0:
            raise ValueError(
                f"RevocationEvent: revoked_at must be > 0, got {self.revoked_at}"
            )


def create_grant(
    principal_id: str,
    capability_name: str,
    scope: str,
    ttl_seconds: float,
    max_uses: Optional[int] = None,
    revocable: bool = True,
) -> Grant:
    """
    Create a Grant.

    Parameters:
    - principal_id: Principal identifier
    - capability_name: Name of capability to grant
    - scope: Explicit scope string
    - ttl_seconds: Time-to-live in seconds
    - max_uses: Optional maximum use count
    - revocable: Whether Grant can be revoked

    Returns:
        Immutable Grant object
    """
    now = time.monotonic()
    grant_id = str(uuid.uuid4())
    expires_at = now + ttl_seconds

    grant = Grant(
        grant_id=grant_id,
        principal_id=principal_id,
        capability_name=capability_name,
        scope=scope,
        issued_at=now,
        expires_at=expires_at,
        max_uses=max_uses,
        revocable=revocable,
    )

    return grant


def create_revocation(
    grant_id: str,
    revoked_by_principal: str,
    reason: RevocationReason,
) -> RevocationEvent:
    """
    Create a revocation event.

    Parameters:
    - grant_id: Grant to revoke
    - revoked_by_principal: Principal revoking
    - reason: Reason for revocation

    Returns:
        Immutable RevocationEvent object
    """
    now = time.monotonic()

    return RevocationEvent(
        grant_id=grant_id,
        revoked_by_principal=revoked_by_principal,
        reason=reason,
        revoked_at=now,
    )
