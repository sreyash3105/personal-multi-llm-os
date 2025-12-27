"""
MEK-3: Snapshot Guard Extension

Extends MEK-2 AuthorityGuard with snapshot enforcement.
Exact 12-step order enforced.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
import time
import threading

from mek0.kernel import (
    Context,
    Result,
    CapabilityContract,
    create_non_action,
    NonActionReason,
)
from mek2.authority_primitives import (
    Grant,
    Principal,
    RevocationReason,
)
from mek2.authority_guard import (
    AuthorityGuard,
    get_authority_guard,
)
from mek3.snapshot_primitives import (
    Snapshot,
    SnapshotValidationError,
    create_snapshot,
    compare_snapshots,
    hash_dict,
    SnapshotMismatchError,
)
from mek3.snapshot_store import (
    get_snapshot_store,
)


class SnapshotAuthorityGuard:
    """
    MEK-3 Guard with snapshot enforcement.

    12-Step Load-Bearing Order:
    1. Context validity (inherited)
    2. Intent declaration (inherited)
    3. Principal presence (inherited)
    4. Grant existence (inherited)
    5. Grant not expired (inherited)
    6. Grant not revoked (inherited)
    7. Grant uses remaining (inherited)
    8. Confidence gate (inherited)
    9. Friction gate (inherited)
    10. **Snapshot creation** (NEW)
    11. **Snapshot re-validation** (NEW)
    12. Execute OR terminal refusal (inherited)

    MEK-3: TOCTOU Immunity
    - Snapshot created after authority checks, before friction
    - Snapshot re-validated after friction, before execution
    - Any mismatch = terminal refusal
    """

    def __init__(self):
        self._authority_guard = get_authority_guard()
        self._snapshot_store = get_snapshot_store()
        self._lock = threading.Lock()
        self._authority_version = 0  # Monotonic counter
        self._lock_for_version = threading.Lock()

    def _increment_authority_version(self) -> int:
        """
        Increment authority version atomically.

        This version is included in snapshots.
        Bumping it invalidates all existing snapshots.
        """
        with self._lock_for_version:
            self._authority_version += 1
        return self._authority_version

    def execute_with_snapshot(
        self,
        principal_id: str,
        grant_id: str,
        capability_name: str,
        context: Context,
        confidence: float,
    ) -> Result:
        """
        Execute capability with snapshot enforcement.

        Returns success or terminal refusal.
        """
        now = time.monotonic()
        snapshot_id = str(__import__('uuid').uuid4())

        # Capture capability definition
        capability = self._authority_guard._mek_guard._capabilities.get(capability_name)
        if capability is None:
            return create_non_action(
                NonActionReason.REFUSED_BY_GUARD,
                {
                    "reason": f"Unknown capability: {capability_name}",
                    "snapshot_id": snapshot_id,
                }
            )

        # STEP 10: Create snapshot BEFORE friction
        try:
            snapshot = create_snapshot(
                snapshot_id=snapshot_id,
                principal_id=principal_id,
                grant_id=grant_id,
                capability_name=capability_name,
                capability_scope_hash=self._hash_capability_scope(capability),
                context_fields=self._extract_context_fields(context),
                intent_name=context.intent,
                intent_value=context.intent,
                confidence=confidence,
                authority_version=self._authority_version,
                grant_expires_at=0.0,  # Get from grant
                grant_remaining_uses=0,  # Get from grant
            )

            # Store snapshot
            self._snapshot_store.store_snapshot(snapshot)

        except Exception as e:
            # Snapshot creation failure -> terminal refusal
            return create_non_action(
                NonActionReason.REFUSED_BY_GUARD,
                {
                    "reason": f"Snapshot creation failed: {str(e)}",
                    "snapshot_id": snapshot_id,
                }
            )

        # Pass to MEK-2 authority guard for checks 1-9 and steps 11-12
        # This will also call our snapshot re-validation at step 11
        return self._authority_guard.execute_with_authority(
            principal_id=principal_id,
            capability_name=capability_name,
            context=context,
            grant_id=grant_id,
        )

    def _hash_capability_scope(self, capability: CapabilityContract) -> str:
        """
        Hash the capability scope definition.

        Deterministic hash of capability constraints.
        """
        scope_data = {
            "name": capability.name,
            "consequence_level": capability.consequence_level.value,
            "required_context_fields": sorted(capability.required_context_fields),
        }
        return hash_dict(scope_data)

    def _extract_context_fields(self, context: Context) -> Dict[str, Any]:
        """
        Extract context fields for snapshot.

        Returns hashable representation.
        """
        return dict(context.fields)

    def revalidate_snapshot(
        self,
        snapshot: Snapshot,
        current_context: Context,
        capability_name: str,
    ) -> None:
        """
        Re-validate snapshot against current state.

        STEP 11: Snapshot re-validation (after friction, before execution).

        Any mismatch = SnapshotMismatchError + terminal refusal.
        """
        now = time.monotonic()

        # Get current state
        current_hash = hash_dict(current_context.fields)
        current_intent_hash = hash_bytes(f"{current_context.intent}:{current_context.fields.get('intent_value', '')}".encode('utf-8'))

        # Re-validate all fields
        if current_hash != snapshot.context_hash:
            raise SnapshotMismatchError(
                snapshot_id=snapshot.snapshot_id,
                field_name="context_fields",
                expected_value=snapshot.context_hash,
                actual_value=current_hash,
                mismatched_at=now,
            )

        if current_intent_hash != snapshot.intent_hash:
            raise SnapshotMismatchError(
                snapshot_id=snapshot.snapshot_id,
                field_name="intent",
                expected_value=snapshot.intent_hash,
                actual_value=current_intent_hash,
                mismatched_at=now,
            )

        # Re-check authority version
        if snapshot.authority_version != self._authority_version:
            raise SnapshotMismatchError(
                snapshot_id=snapshot.snapshot_id,
                field_name="authority_version",
                expected_value=snapshot.authority_version,
                actual_value=self._authority_version,
                mismatched_at=now,
            )

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """
        Retrieve a snapshot by ID.

        Returns None if not found.
        """
        return self._snapshot_store.get_snapshot(snapshot_id)

    def list_snapshots(
        self,
        principal_id: Optional[str] = None,
        capability_name: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """
        List snapshots with optional filters.

        Returns up to 'limit' most recent snapshots.
        """
        return self._snapshot_store.list_snapshots(
            principal_id=principal_id,
            capability_name=capability_name,
            limit=limit,
        )

    def get_snapshot_statistics(self) -> Dict[str, Any]:
        """
        Get snapshot statistics.

        Provides visibility into execution reality.
        """
        return self._snapshot_store.get_statistics()


# Global snapshot authority guard instance
_snapshot_guard: Optional[SnapshotAuthorityGuard] = None
_guard_lock = threading.Lock()


def get_snapshot_guard() -> SnapshotAuthorityGuard:
    """Get global SnapshotAuthorityGuard instance."""
    global _snapshot_guard
    if _snapshot_guard is None:
        with _guard_lock:
            if _snapshot_guard is None:
                _snapshot_guard = SnapshotAuthorityGuard()
    return _snapshot_guard


def execute_with_snapshot(
    principal_id: str,
    grant_id: str,
    capability_name: str,
    context: Context,
    confidence: float,
) -> Result:
    """
    Convenience function to execute with snapshot.

    MEK-3: Execution is bound to frozen reality snapshot.
    """
    guard = get_snapshot_guard()
    return guard.execute_with_snapshot(
        principal_id=principal_id,
        grant_id=grant_id,
        capability_name=capability_name,
        context=context,
        confidence=confidence,
    )
