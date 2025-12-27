"""
MEK-3: Snapshot Store

In-memory, append-only snapshot storage.
Snapshots are evidence, not permission.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
import threading
import time

from .snapshot_primitives import Snapshot, SnapshotValidationError


class SnapshotStore:
    """
    In-memory snapshot store.

    MEK-3: Snapshots are append-only.
    - No mutation, no deletion
    - No granting of authority
    - Evidence only, not permission
    """

    def __init__(self):
        self._snapshots: Dict[str, Snapshot] = {}
        self._lock = threading.Lock()

    def store_snapshot(self, snapshot: Snapshot) -> None:
        """
        Store a snapshot.

        Snapshots are immutable once stored.
        No deletion allowed.
        """
        with self._lock:
            if snapshot.snapshot_id in self._snapshots:
                raise ValueError(
                    f"Snapshot {snapshot.snapshot_id} already exists"
                )

            self._snapshots[snapshot.snapshot_id] = snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """
        Retrieve a snapshot by ID.

        Returns None if not found.
        """
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def list_snapshots(
        self,
        principal_id: Optional[str] = None,
        capability_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Snapshot]:
        """
        List snapshots with optional filters.

        Returns up to 'limit' most recent snapshots.
        """
        with self._lock:
            filtered = list(self._snapshots.values())

            if principal_id is not None:
                filtered = [s for s in filtered if s.principal_id == principal_id]

            if capability_name is not None:
                filtered = [s for s in filtered if s.capability_name == capability_name]

            # Sort by captured_at (newest first)
            filtered.sort(key=lambda s: s.captured_at, reverse=True)

            return filtered[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get snapshot statistics.

        Returns counts by principal, capability, and confidence range.
        """
        with self._lock:
            snapshots = list(self._snapshots.values())

        # Count by principal
        by_principal: Dict[str, int] = {}
        for s in snapshots:
            by_principal[s.principal_id] = by_principal.get(s.principal_id, 0) + 1

        # Count by capability
        by_capability: Dict[str, int] = {}
        for s in snapshots:
            by_capability[s.capability_name] = by_capability.get(s.capability_name, 0) + 1

        # Count by confidence range
        by_confidence: Dict[str, int] = {}
        for s in snapshots:
            by_confidence[s.confidence_range] = by_confidence.get(s.confidence_range, 0) + 1

        return {
            "total_snapshots": len(snapshots),
            "by_principal": by_principal,
            "by_capability": by_capability,
            "by_confidence_range": by_confidence,
        }


# Global snapshot store instance
_snapshot_store: Optional[SnapshotStore] = None
_store_lock = threading.Lock()


def get_snapshot_store() -> SnapshotStore:
    """Get global snapshot store instance."""
    global _snapshot_store
    if _snapshot_store is None:
        with _store_lock:
            if _snapshot_store is None:
                _snapshot_store = SnapshotStore()
    return _snapshot_store
