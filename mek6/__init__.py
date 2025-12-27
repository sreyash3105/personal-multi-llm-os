"""
MEK-6: Evidence Export (Read-Only Proof Bundles)

Verifiable proof bundles.
Evidence is proof, not narrative.
"""

from typing import Any

from evidence_bundle import (
    # Snapshots
    ContextSnapshot,
    IntentSnapshot,
    PrincipalSnapshot,
    GrantSnapshot,
    ExecutionSnapshot,
    # Bundle and Result
    EvidenceBundle,
    VerificationResult,
    # Factory functions
    create_evidence_bundle,
    create_context_snapshot,
    create_intent_snapshot,
    create_principal_snapshot,
    create_grant_snapshot,
    create_execution_snapshot,
)
from hash_chain import (
    HashChain,
    hash_value,
    verify_hash,
)
from export_interface import (
    EvidenceExporter,
    EvidenceExportError,
    EvidenceVerificationError,
    get_evidence_exporter,
    export_bundle_to_file,
    verify_bundle_from_file,
)
from evidence_exporter import (
    EvidenceGuard,
    get_evidence_guard,
)


__all__ = [
    # Snapshots
    "ContextSnapshot",
    "IntentSnapshot",
    "PrincipalSnapshot",
    "GrantSnapshot",
    "ExecutionSnapshot",
    # Bundle and Result
    "EvidenceBundle",
    "VerificationResult",
    # Factory functions
    "create_evidence_bundle",
    "create_context_snapshot",
    "create_intent_snapshot",
    "create_principal_snapshot",
    "create_grant_snapshot",
    "create_execution_snapshot",
    # Hash Chain
    "HashChain",
    "hash_value",
    "verify_hash",
    # Export
    "EvidenceExporter",
    "EvidenceExportError",
    "EvidenceVerificationError",
    "get_evidence_exporter",
    "export_bundle_to_file",
    "verify_bundle_from_file",
    # Evidence Guard
    "EvidenceGuard",
    "get_evidence_guard",
]


def capture_evidence(
    guard: Any,
    capability_name: str,
    context: dict,
    principal_id: str,
    grant_id: str = None,  # type: ignore
    grant_data: dict = None,  # type: ignore
) -> dict:
    """
    Capture evidence during execution.

    Args:
        guard: MEK SnapshotAuthorityGuard
        capability_name: Capability to execute
        context: Execution context
        principal_id: Principal ID
        grant_id: Grant ID (optional)
        grant_data: Grant data (optional)

    Returns:
        Execution result with evidence
    """
    from evidence_exporter import get_evidence_guard

    ev_guard = get_evidence_guard(guard)
    return ev_guard.execute_with_evidence_capture(
        capability_name=capability_name,
        context=context,
        principal_id=principal_id,
        grant_id=grant_id,
        grant_data=grant_data,
    )
