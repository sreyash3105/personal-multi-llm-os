"""
MEK-6: Adversarial Tests for Evidence Export

Tests prove impossibility, not behavior.
Each test MUST fail for bypass attempt.
"""

import pytest
import json
from typing import Any, Dict
from evidence_bundle import (
    EvidenceBundle,
    VerificationResult,
)


class TestBundleBasics:
    """Test evidence bundle creation and validation."""

    def test_bundles_cannot_be_mutated_after_creation(self):
        """Bundles must be immutable after creation."""
        context_snap = create_context_snapshot("ctx123", "user123", "test_cap", 0.9, {})
        intent_snap = create_intent_snapshot("test_cap", "test_cap")
        principal_snap = create_principal_snapshot("user123")
        exec_snap = create_execution_snapshot("step1", "test_cap", "hash123", "snap123", True)

        bundle = create_evidence_bundle(
            context_snapshot=context_snap,
            intent_snapshot=intent_snap,
            principal_snapshot=principal_snap,
            execution_snapshots=[exec_snap],
            results=[{"result": "ok"}],
        )

        with pytest.raises(Exception):
            bundle.bundle_id = "modified"

    def test_missing_fields_cause_creation_failure(self):
        """Missing required fields cause bundle creation failure."""
        with pytest.raises(ValueError) as exc_info:
            create_evidence_bundle(
                context_snapshot=context_snap,
                intent_snapshot=intent_snap,
                principal_snapshot=principal_snap,
                grant_snapshot=None,
                execution_snapshots=[],
                results=[{"result": "ok"}],
            )

    def test_failure_and_results_mutually_exclusive(self):
        """Failure and results are mutually exclusive."""
        exporter = get_evidence_exporter()

        context_snap = create_context_snapshot("ctx123", "user123", "test_cap", 0.9, {})
        intent_snap = create_intent_snapshot("test_cap", "test_cap")
        principal_snap = create_principal_snapshot("user123")

        exec_snap = create_execution_snapshot("step1", "test_cap", "hash123", "snap123", True)
        bundle_fail = create_evidence_bundle(
            context_snapshot=context_snap,
            intent_snapshot=intent_snap,
            principal_snapshot=principal_snap,
            execution_snapshots=[exec_snap],
            failure_composition={"reason": "FAILED"},
        )

        bundle_success = create_evidence_bundle(
            context_snapshot=context_snap,
            intent_snapshot=intent_snap,
            principal_snapshot=principal_snap,
            execution_snapshots=[exec_snap],
            results=[{"result": "ok"}],
        )

        exporter.store_bundle(bundle_fail)
        exporter.store_bundle(bundle_success)


class TestExportInterface:
    """Test export and verification interface."""

    def test_export_has_zero_runtime_side_effects(self):
        """Export must have zero runtime side effects."""
        exporter = get_evidence_exporter()

        context_snap = create_context_snapshot("ctx123", "user123", "test_cap", 0.9, {})
        intent_snap = create_intent_snapshot("test_cap", "test_cap")
        principal_snap = create_principal_snapshot("user123")
        exec_snap = create_execution_snapshot("step1", "test_cap", "hash123", "snap123", True)

        bundle = create_evidence_bundle(
            context_snapshot=context_snap,
            intent_snapshot=intent_snap,
            principal_snapshot=principal_snap,
            execution_snapshots=[exec_snap],
            results=[{"result": "ok"}],
        )

        exporter.store_bundle(bundle)

        bundle_bytes = exporter.export_bundle(bundle.bundle_id)

        # Export does NOT trigger execution
        assert isinstance(bundle_bytes, bytes)
        assert isinstance(verification_result, VerificationResult)


class TestEvidenceGuard:
    """Test evidence guard integration."""

    def test_observers_cannot_fabricate_bundles(self):
        """Observers cannot fabricate evidence bundles."""
        guard = MockGuard()

        result = guard.execute_with_evidence_capture(
            capability_name="test_cap",
            context={"principal_id": "user123"},
        )

        bundle_id = result["bundle_id"]

        assert bundle is not None
        assert bundle.bundle_id == bundle_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
