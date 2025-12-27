"""
MEK-3: Execution Snapshot & Reality-Binding

State-as-Evidence. TOCTOU Immunity. Anti-rationalization.
"""

from .snapshot_primitives import (
    Snapshot,
    SnapshotValidationError,
    SnapshotMismatchError,
    SnapshotHashAlgorithm,
    create_snapshot,
    compare_snapshots,
    hash_dict,
    hash_bytes,
)

from .snapshot_store import (
    SnapshotStore,
    get_snapshot_store,
)

from .snapshot_guard import (
    SnapshotAuthorityGuard,
    get_snapshot_guard,
    execute_with_snapshot,
)

__version__ = "0.1.0"
__all__ = [
    # Snapshot primitives
    "Snapshot",
    "SnapshotValidationError",
    "SnapshotMismatchError",
    "SnapshotHashAlgorithm",
    "create_snapshot",
    "compare_snapshots",
    "hash_dict",
    "hash_bytes",
    # Snapshot store
    "SnapshotStore",
    "get_snapshot_store",
    # Snapshot guard
    "SnapshotAuthorityGuard",
    "get_snapshot_guard",
    "execute_with_snapshot",
]
