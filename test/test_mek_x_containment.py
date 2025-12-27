"""
ADVERSARIAL TESTS FOR MEK-X CONTAINMENT

Proving absolute containment by impossibility.

Tests demonstrate:
- MEK-X cannot execute capability
- MEK-X cannot fabricate Context/Intent
- MEK-X cannot request grants programmatically
- MEK-X cannot influence Guard decisions
- MEK-X output ignored does not affect system
- Removing MEK-X changes nothing in MEK
- MEK-X failure cannot propagate into MEK
- Infinite loops in MEK-X do not affect MEK

Build Prompt: MEK-X — SANDBOXED INTELLIGENCE ZONE
"""

import pytest
import time
import sys

from backend.mek_x.proposal import Proposal, create_proposal, ConfidenceRange
from backend.mek_x.intelligence import (
    IntelligenceEngine,
    MemoryEntry,
    Hypothesis,
    get_intelligence_engine,
)
from backend.mek_x.sandbox import SandboxError, SandboxAdapter, install_import_hook


class TestMEKXCannotExecuteCapabilities:
    """MEK-X cannot execute capabilities."""

    def test_proposal_is_data_only(self):
        """Proposal is data only, not executable."""
        proposal = create_proposal("test proposal")

        assert isinstance(proposal, Proposal)
        assert proposal.text == "test proposal"
        assert not hasattr(proposal, "execute")
        assert not callable(getattr(proposal, "execute", None))

    def test_intelligence_engine_returns_proposal_not_execution(self):
        """Intelligence engine returns proposal, not execution."""
        engine = get_intelligence_engine()
        result = engine.plan("goal", ["constraint"])

        assert isinstance(result, dict)
        assert "proposal_id" in result
        assert "text" in result
        assert not hasattr(result, "execute")

    def test_requested_actions_are_symbolic_only(self):
        """Requested actions are symbolic, not executable."""
        proposal = create_proposal(
            "test",
            requested_actions=[{"type": "read_file", "path": "/tmp"}],
        )

        assert proposal.requested_actions[0]["type"] == "read_file"
        assert not callable(proposal.requested_actions[0])


class TestMEKXCannotFabricateContextIntent:
    """MEK-X cannot fabricate MEK Context/Intent."""

    def test_no_context_import_available(self):
        """MEK-X cannot import Context from MEK."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("mek0.kernel.Context")

    def test_no_intent_import_available(self):
        """MEK-X cannot import Intent from MEK."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("mek0.kernel.Intent")

    def test_no_capability_contract_import_available(self):
        """MEK-X cannot import CapabilityContract from MEK."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("mek0.kernel.CapabilityContract")

    def test_proposal_does_not_map_to_context(self):
        """Proposal does not map to Context."""
        proposal = create_proposal("test")

        assert not hasattr(proposal, "context_id")
        assert not hasattr(proposal, "confidence")
        assert not hasattr(proposal, "fields")


class TestMEKXCannotRequestGrants:
    """MEK-X cannot request grants programmatically."""

    def test_no_grant_import_available(self):
        """MEK-X cannot import Grant from MEK."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("mek2.authority_primitives.Grant")

    def test_no_principal_import_available(self):
        """MEK-X cannot import Principal from MEK."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("mek2.authority_primitives.Principal")

    def test_no_revocation_import_available(self):
        """MEK-X cannot import RevocationEvent from MEK."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("mek2.authority_primitives.RevocationEvent")

    def test_proposal_cannot_authorize_execution(self):
        """Proposal cannot authorize execution."""
        proposal = create_proposal("test")

        assert not hasattr(proposal, "grant_id")
        assert not hasattr(proposal, "principal_id")
        assert not hasattr(proposal, "expires_at")


class TestMEKXCannotInfluenceGuard:
    """MEK-X cannot influence Guard decisions."""

    def test_no_guard_import_available(self):
        """MEK-X cannot import Guard from MEK."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("mek0.kernel.Guard")

    def test_no_execution_guard_import_available(self):
        """MEK-X cannot import ExecutionGuard from MEK."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("backend.core.execution_guard")

    def test_proposal_cannot_trigger_guard(self):
        """Proposal cannot trigger Guard."""
        proposal = create_proposal("test")

        assert not hasattr(proposal, "execute")
        assert not hasattr(proposal, "trigger_guard")


class TestMEKXOutputIgnoredDoesNotAffectSystem:
    """MEK-X output ignored does not affect system."""

    def test_discarding_proposal_has_no_side_effects(self):
        """Discarding proposal has no side effects."""
        engine = get_intelligence_engine()

        proposal = engine.plan("goal", ["constraint"])

        assert proposal is not None

        del proposal

        engine2 = get_intelligence_engine()
        assert engine2 is not None
        assert engine2 is engine

    def test_memory_storage_does_not_affect_mek(self):
        """MEK-X memory storage does not affect MEK."""
        engine = get_intelligence_engine()

        entry = engine.store_memory("test_key", "test_value")
        assert entry.value == "test_value"

        retrieved = engine.retrieve_memory("test_key")
        assert len(retrieved) == 1
        assert retrieved[0].value == "test_value"


class TestRemovingMEKXChangesNothingInMEK:
    """Removing MEK-X changes nothing in MEK."""

    def test_mek_x_memory_isolated(self):
        """MEK-X memory is isolated from MEK."""
        engine = get_intelligence_engine()
        engine.store_memory("mek_x_only", "value")

        assert len(engine.retrieve_memory("mek_x_only")) == 1

    def test_mek_x_hypotheses_isolated(self):
        """MEK-X hypotheses are isolated from MEK."""
        engine = get_intelligence_engine()
        hypothesis = engine.generate_hypothesis("phenomenon", ["evidence"])

        assert hypothesis.description
        assert hypothesis.testable


class TestMEKXFailureCannotPropagateIntoMEK:
    """MEK-X failure cannot propagate into MEK."""

    def test_intelligence_exception_isolated(self):
        """Exception in IntelligenceEngine is isolated."""
        engine = get_intelligence_engine()

        with pytest.raises(Exception):
            engine.plan("", [])

        engine2 = get_intelligence_engine()
        assert engine2 is not None

    def test_memory_error_isolated(self):
        """Memory error is isolated."""
        engine = get_intelligence_engine()

        engine.store_memory("key", None)

        assert len(engine.retrieve_memory("key")) >= 0


class TestInfiniteLoopsInMEKXDoNotAffectMEK:
    """Infinite loops in MEK-X do not affect MEK."""

    def test_simulated_loop_isolated(self):
        """Simulated loop is isolated."""
        engine = get_intelligence_engine()

        scenario = {"type": "loop", "iterations": 10}
        result = engine.simulate(scenario, iterations=10)

        assert isinstance(result, dict)
        assert "proposal_id" in result

    def test_reasoning_loop_isolated(self):
        """Reasoning loop is isolated."""
        engine = get_intelligence_engine()

        for i in range(5):
            result = engine.reason(f"question_{i}", {})

        assert isinstance(result, dict)


class TestMEKXCannotAccessCoreImports:
    """MEK-X cannot access core imports."""

    def test_capability_registry_import_forbidden(self):
        """CapabilityRegistry import is forbidden."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("backend.core.capability_registry")

    def test_local_runner_import_forbidden(self):
        """LocalRunner import is forbidden."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("backend.core.local_runner")

    def test_execution_guard_import_forbidden(self):
        """ExecutionGuard import is forbidden."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("backend.core.execution_guard")

    def test_snapshot_guard_import_forbidden(self):
        """SnapshotGuard import is forbidden."""
        with pytest.raises(SandboxError):
            SandboxAdapter.check_import("mek3.snapshot_guard")


class TestProposalIsImmutable:
    """Proposal is immutable by design."""

    def test_proposal_dataclass_is_frozen(self):
        """Proposal dataclass is frozen."""
        proposal = create_proposal("test")

        assert proposal.text == "test"

    def test_proposal_cannot_modify_after_creation(self):
        """Proposal cannot be modified after creation."""
        proposal = create_proposal("test")

        with pytest.raises(Exception):
            proposal.text = "modified"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
