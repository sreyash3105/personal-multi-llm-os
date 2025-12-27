"""
MEK-2: Authority Primitives & Guard Extensions

Principal, Grant, Revocation - time-bound authority.
No intelligence. No autonomy. Authority is data + enforcement.
"""

from .authority_primitives import (
    Principal,
    Grant,
    RevocationEvent,
    RevocationReason,
    create_principal,
    create_grant,
    create_revocation,
    decrement_grant_use,
)

from .authority_guard import (
    AuthorityGuard,
    AuthorityState,
    get_authority_guard,
    get_authority_state,
)

__version__ = "0.1.0"
__all__ = [
    # Authority primitives
    "Principal",
    "Grant",
    "RevocationEvent",
    "RevocationReason",
    "create_principal",
    "create_grant",
    "create_revocation",
    "decrement_grant_use",
    # Authority guard
    "AuthorityGuard",
    "AuthorityState",
    "get_authority_guard",
    "get_authority_state",
]
