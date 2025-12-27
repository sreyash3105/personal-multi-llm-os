"""
MEK-6: Export Interface

Read-only export and verification.
Export does NOT trigger execution.
"""

import json
from typing import Any, Dict, List, Optional

from evidence_bundle import EvidenceBundle, VerificationResult
from hash_chain import HashChain


class EvidenceExportError(Exception):
    """
    Raised when evidence export fails.
    """

    pass


class EvidenceVerificationError(Exception):
    """
    Raised when evidence verification fails.
    """

    pass


class EvidenceExporter:
    """
    Read-only export interface.

    Export does NOT trigger execution.
    Verification performs only structural + hash checks.
    """

    def __init__(self):
        """
        Initialize evidence exporter.
        """
        self.bundles: Dict[str, EvidenceBundle] = {}

    def store_bundle(self, bundle: EvidenceBundle) -> None:
        """
        Store evidence bundle.

        Args:
            bundle: Bundle to store
        """
        self.bundles[bundle.bundle_id] = bundle

    def export_bundle(self, bundle_id: str) -> bytes:
        """
        Export evidence bundle to bytes.

        Args:
            bundle_id: Bundle ID to export

        Returns:
            Serialized bundle as bytes

        Raises:
            EvidenceExportError: If bundle not found or export fails
        """
        if bundle_id not in self.bundles:
            raise EvidenceExportError(f"Bundle not found: {bundle_id}")

        bundle = self.bundles[bundle_id]

        try:
            # Serialize to JSON
            serialized = self._serialize_bundle(bundle)
            return serialized.encode("utf-8")
        except Exception as e:
            raise EvidenceExportError(f"Export failed: {e}")

    def export_all_bundles(self) -> bytes:
        """
        Export all bundles to bytes.

        Returns:
            Serialized all bundles as bytes
        """
        all_bundles = {
            bundle_id: json.loads(self.export_bundle(bundle_id).decode("utf-8"))
            for bundle_id in self.bundles
        }

        return json.dumps(all_bundles, indent=2).encode("utf-8")

    def verify_bundle(self, bundle_bytes: bytes) -> VerificationResult:
        """
        Verify evidence bundle.

        Performs only structural + hash checks.
        Never evaluates "correctness".

        Args:
            bundle_bytes: Serialized bundle bytes

        Returns:
            VerificationResult with validation results
        """
        try:
            # Deserialize bundle
            bundle_dict = json.loads(bundle_bytes.decode("utf-8"))
            bundle = self._deserialize_bundle(bundle_dict)
        except Exception as e:
            return VerificationResult(
                is_valid=False,
                bundle_id="unknown",
                hash_valid=False,
                structure_valid=False,
                integrity_valid=False,
                errors=[f"Deserialization failed: {e}"],
            )

        errors = []

        # 1. Verify structure
        structure_valid = self._verify_structure(bundle)
        if not structure_valid:
            errors.append("Structure validation failed")

        # 2. Verify hash chain
        hash_valid = self._verify_hash_chain(bundle)
        if not hash_valid:
            errors.append("Hash chain verification failed")

        # 3. Verify integrity
        integrity_valid = self._verify_integrity(bundle)
        if not integrity_valid:
            errors.append("Integrity verification failed")

        is_valid = structure_valid and hash_valid and integrity_valid

        return VerificationResult(
            is_valid=is_valid,
            bundle_id=bundle.bundle_id,
            hash_valid=hash_valid,
            structure_valid=structure_valid,
            integrity_valid=integrity_valid,
            errors=errors,
        )

    def _serialize_bundle(self, bundle: EvidenceBundle) -> str:
        """
        Serialize bundle to JSON.

        Args:
            bundle: Bundle to serialize

        Returns:
            JSON string
        """
        bundle_dict = {
            "bundle_id": bundle.bundle_id,
            "created_at": bundle.created_at,
            "context_snapshot": self._serialize_snapshot(bundle.context_snapshot),
            "intent_snapshot": self._serialize_snapshot(bundle.intent_snapshot),
            "principal_snapshot": self._serialize_snapshot(bundle.principal_snapshot),
            "grant_snapshot": self._serialize_snapshot(bundle.grant_snapshot) if bundle.grant_snapshot else None,
            "execution_snapshots": [self._serialize_snapshot(s) for s in bundle.execution_snapshots],
            "failure_composition": bundle.failure_composition,
            "results": bundle.results,
            "authority_version": bundle.authority_version,
            "hash_chain_root": bundle.hash_chain_root,
        }

        return json.dumps(bundle_dict, sort_keys=True, separators=(",", ":"))

    def _deserialize_bundle(self, bundle_dict: Dict[str, Any]) -> EvidenceBundle:
        """
        Deserialize bundle from dict.

        Args:
            bundle_dict: Bundle dictionary

        Returns:
            EvidenceBundle
        """
        from evidence_bundle import (
            ContextSnapshot,
            IntentSnapshot,
            PrincipalSnapshot,
            GrantSnapshot,
            ExecutionSnapshot,
        )

        return EvidenceBundle(
            bundle_id=bundle_dict["bundle_id"],
            created_at=bundle_dict["created_at"],
            context_snapshot=ContextSnapshot(**bundle_dict["context_snapshot"]),
            intent_snapshot=IntentSnapshot(**bundle_dict["intent_snapshot"]),
            principal_snapshot=PrincipalSnapshot(**bundle_dict["principal_snapshot"]),
            grant_snapshot=GrantSnapshot(**bundle_dict["grant_snapshot"]) if bundle_dict.get("grant_snapshot") else None,
            execution_snapshots=[
                ExecutionSnapshot(**s) for s in bundle_dict["execution_snapshots"]
            ],
            failure_composition=bundle_dict.get("failure_composition"),
            results=bundle_dict.get("results"),
            authority_version=bundle_dict["authority_version"],
            hash_chain_root=bundle_dict["hash_chain_root"],
        )

    def _serialize_snapshot(self, snapshot: Any) -> Dict[str, Any]:
        """
        Serialize snapshot to dict.

        Args:
            snapshot: Snapshot to serialize

        Returns:
            Snapshot as dict
        """
        if snapshot is None:
            return None

        if hasattr(snapshot, "__dict__"):
            return snapshot.__dict__

        return snapshot

    def _verify_structure(self, bundle: EvidenceBundle) -> bool:
        """
        Verify bundle structure.

        Args:
            bundle: Bundle to verify

        Returns:
            True if structure is valid
        """
        try:
            if not bundle.bundle_id:
                return False

            if not bundle.created_at:
                return False

            if not bundle.context_snapshot:
                return False

            if not bundle.intent_snapshot:
                return False

            if not bundle.principal_snapshot:
                return False

            if not bundle.authority_version:
                return False

            if not bundle.hash_chain_root:
                return False

            has_failure = bundle.failure_composition is not None
            has_results = bundle.results is not None

            # Exactly one of failure_composition or results must be present
            if (has_failure and has_results) or (not has_failure and not has_results):
                return False

            return True
        except Exception:
            return False

    def _verify_hash_chain(self, bundle: EvidenceBundle) -> bool:
        """
        Verify hash chain.

        Args:
            bundle: Bundle to verify

        Returns:
            True if hash chain is valid
        """
        try:
            # Rebuild hash chain from bundle
            hash_chain = HashChain()
            hash_chain.add_element("context", bundle.context_snapshot)
            hash_chain.add_element("intent", bundle.intent_snapshot)
            hash_chain.add_element("principal", bundle.principal_snapshot)

            if bundle.grant_snapshot:
                hash_chain.add_element("grant", bundle.grant_snapshot)

            for i, exec_snap in enumerate(bundle.execution_snapshots):
                hash_chain.add_element(f"execution_{i}", exec_snap)

            if bundle.failure_composition:
                hash_chain.add_element("failure", bundle.failure_composition)

            if bundle.results:
                hash_chain.add_element("results", bundle.results)

            hash_chain.add_element("authority_version", bundle.authority_version)

            # Verify root matches
            return hash_chain.verify(bundle.hash_chain_root)
        except Exception:
            return False

    def _verify_integrity(self, bundle: EvidenceBundle) -> bool:
        """
        Verify bundle integrity.

        Args:
            bundle: Bundle to verify

        Returns:
            True if integrity is valid
        """
        try:
            # Verify all required fields are present
            if not bundle.bundle_id:
                return False

            if not bundle.hash_chain_root:
                return False

            # Verify bundle is immutable
            if not hasattr(bundle, "__dataclass_fields__"):
                return False

            return True
        except Exception:
            return False


def get_evidence_exporter() -> EvidenceExporter:
    """
    Get evidence exporter instance.

    Returns:
        EvidenceExporter instance
    """
    return EvidenceExporter()


def export_bundle_to_file(
    exporter: EvidenceExporter,
    bundle_id: str,
    filepath: str
) -> None:
    """
    Export bundle to file.

    Args:
        exporter: EvidenceExporter instance
        bundle_id: Bundle ID to export
        filepath: Output file path

    Raises:
        EvidenceExportError: If export fails
    """
    bundle_bytes = exporter.export_bundle(bundle_id)

    with open(filepath, "wb") as f:
        f.write(bundle_bytes)


def verify_bundle_from_file(
    exporter: EvidenceExporter,
    filepath: str
) -> VerificationResult:
    """
    Verify bundle from file.

    Args:
        exporter: EvidenceExporter instance
        filepath: Bundle file path

    Returns:
        VerificationResult
    """
    with open(filepath, "rb") as f:
        bundle_bytes = f.read()

    return exporter.verify_bundle(bundle_bytes)
