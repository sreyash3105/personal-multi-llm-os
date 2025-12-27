
from hash_chain import hash_value
from export_interface import EvidenceExporter, get_evidence_exporter
"""
MEK-6: Evidence Exporter

Guard integration for evidence bundle creation.
Evidence bundle is created after execution halts.
"""

import uuid
from typing import Any, Dict, List, Optional

from evidence_bundle import (
    EvidenceBundle,
    ContextSnapshot,
    IntentSnapshot,
    PrincipalSnapshot,
    GrantSnapshot,
    ExecutionSnapshot,
    create_evidence_bundle,
    create_context_snapshot,
    create_intent_snapshot,
    create_principal_snapshot,
    create_grant_snapshot,
    create_execution_snapshot,
)
from export_interface import EvidenceExporter, get_evidence_exporter


class EvidenceGuard:
    """
    Guard extension for evidence export.

    Creates evidence bundles after execution halts.
    Export does NOT trigger execution.
    """

    def __init__(self, guard: Any, exporter: Optional[EvidenceExporter] = None):
        """
        Initialize with MEK Guard.

        Args:
            guard: MEK SnapshotAuthorityGuard from MEK-3
            exporter: EvidenceExporter (default: new instance)
        """
        self.guard = guard
        self.exporter = exporter or get_evidence_exporter()

    def execute_with_evidence_capture(
        self,
        capability_name: str,
        context: Dict[str, Any],
        principal_id: str,
        grant_id: Optional[str] = None,
        grant_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute capability and capture evidence.

        Creates evidence bundle after execution halts.
        Does NOT trigger execution on export.

        Args:
            capability_name: Capability to execute
            context: Execution context
            principal_id: Principal ID
            grant_id: Grant ID (if applicable)
            grant_data: Grant data (if applicable)

        Returns:
            Execution result with evidence
        """
        # Create snapshots
        context_snap = create_context_snapshot(
            context_id=context.get("context_id", ""),
            principal_id=principal_id,
            intent=capability_name,
            confidence=context.get("confidence", 0.0),
            fields=context,
        )

        intent_snap = create_intent_snapshot(
            intent_name=capability_name,
            capability_name=capability_name,
        )

        principal_snap = create_principal_snapshot(
            principal_id=principal_id,
        )

        grant_snap = None
        if grant_id and grant_data:
            grant_snap = create_grant_snapshot(
                grant_id=grant_id,
                principal_id=principal_id,
                capability_name=capability_name,
                scope=grant_data.get("scope", {}),
                issued_at=grant_data.get("issued_at", 0),
                expires_at=grant_data.get("expires_at", 0),
                remaining_uses=grant_data.get("remaining_uses", -1),
            )

        # Execute through Guard
        try:
            mek_result = self.guard.execute(
                capability_name=capability_name,
                context=context,
            )

            # Create execution snapshot
            exec_snap = create_execution_snapshot(
                step_id=None,
                capability_name=capability_name,
                context_hash=self._hash_context(context),
                snapshot_id=mek_result.get("snapshot_id", ""),
                is_success=mek_result.get("is_success", False),
                result_data=mek_result.get("data") if mek_result.get("is_success", False) else None,
                non_action=mek_result.get("non_action") if not mek_result.get("is_success", False) else None,
            )

            # Create evidence bundle
            if mek_result.get("is_success", False):
                bundle = create_evidence_bundle(
                    context_snapshot=context_snap,
                    intent_snapshot=intent_snap,
                    principal_snapshot=principal_snap,
                    grant_snapshot=grant_snap,
                    execution_snapshots=[exec_snap],
                    results=[mek_result],
                )
            else:
                bundle = create_evidence_bundle(
                    context_snapshot=context_snap,
                    intent_snapshot=intent_snap,
                    principal_snapshot=principal_snap,
                    grant_snapshot=grant_snap,
                    execution_snapshots=[exec_snap],
                    failure_composition=mek_result.get("non_action"),
                )

            # Store bundle
            self.exporter.store_bundle(bundle)

            return {
                "is_success": mek_result.get("is_success", False),
                "data": mek_result.get("data"),
                "snapshot_id": mek_result.get("snapshot_id"),
                "non_action": mek_result.get("non_action"),
                "bundle_id": bundle.bundle_id,
            }
        except Exception as e:
            # Create execution snapshot for error
            exec_snap = create_execution_snapshot(
                step_id=None,
                capability_name=capability_name,
                context_hash=self._hash_context(context),
                snapshot_id="",
                is_success=False,
                non_action={
                    "reason": "EXECUTION_ERROR",
                    "details": {"error": str(e)},
                },
            )

            # Create evidence bundle for error
            bundle = create_evidence_bundle(
                context_snapshot=context_snap,
                intent_snapshot=intent_snap,
                principal_snapshot=principal_snap,
                grant_snapshot=grant_snap,
                execution_snapshots=[exec_snap],
                failure_composition={
                    "reason": "EXECUTION_ERROR",
                    "details": {"error": str(e)},
                },
            )

            # Store bundle
            self.exporter.store_bundle(bundle)

            return {
                "is_success": False,
                "non_action": {
                    "reason": "EXECUTION_ERROR",
                    "details": {"error": str(e)},
                },
                "bundle_id": bundle.bundle_id,
            }

    def get_exported_bundle(self, bundle_id: str) -> EvidenceBundle:
        """
        Get exported evidence bundle.

        Args:
            bundle_id: Bundle ID to retrieve

        Returns:
            EvidenceBundle

        Raises:
            KeyError: If bundle not found
        """
        bundles = self.exporter.bundles
        if bundle_id not in bundles:
            raise KeyError(f"Bundle not found: {bundle_id}")

        return bundles[bundle_id]

    def export_bundle(self, bundle_id: str) -> bytes:
        """
        Export evidence bundle to bytes.

        Args:
            bundle_id: Bundle ID to export

        Returns:
            Serialized bundle as bytes
        """
        return self.exporter.export_bundle(bundle_id)

    def verify_bundle(self, bundle_bytes: bytes):
        """
        Verify evidence bundle.

        Performs only structural + hash checks.
        Never evaluates "correctness".

        Args:
            bundle_bytes: Serialized bundle bytes

        Returns:
            VerificationResult
        """
        return self.exporter.verify_bundle(bundle_bytes)

    def _hash_context(self, context: Dict[str, Any]) -> str:
        """
        Hash context for snapshot.

        Args:
            context: Context to hash

        Returns:
            Hash string
        """
        from hash_chain import hash_value

        return hash_value(context)


def get_evidence_guard(
    guard: Any,
    exporter: Optional[EvidenceExporter] = None
) -> EvidenceGuard:
    """
    Get evidence guard instance.

    Args:
        guard: MEK SnapshotAuthorityGuard
        exporter: EvidenceExporter (optional)

    Returns:
        EvidenceGuard instance
    """
    return EvidenceGuard(guard, exporter)
