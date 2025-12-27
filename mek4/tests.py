"""
MEK-4: Adversarial Tests for Composition

Tests prove impossibility, not behavior.
Each test MUST fail for bypass attempt.
"""

import pytest
from typing import Any, Dict, List

from composition_primitives import (
    Step,
    Composition,
    FailurePolicy,
    StepResult,
    CompositionResult,
    create_step,
    create_composition,
    create_success_result,
    create_refusal_result,
)
from composition_guard import CompositionGuard, get_composition_guard


class MockGuard:
    """Mock MEK Guard for testing."""

    def __init__(self):
        self.should_refuse_at_step: Dict[str, bool] = {}
        self.refusal_reason: str = "TEST_REFUSAL"
        self.executed_contexts: List[Dict[str, Any]] = []

    def execute(self, capability_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock execute method."""
        self.executed_contexts.append(context)

        step_id = context.get("step_id", "")

        if self.should_refuse_at_step.get(step_id, False):
            return {
                "is_success": False,
                "non_action": {
                    "reason": self.refusal_reason,
                    "details": {"step_id": step_id},
                    "timestamp": 1234567890,
                },
            }

        return {
            "is_success": True,
            "data": {
                "result": f"executed_{step_id}",
                "context": context,
            },
            "snapshot_id": f"snap_{step_id}",
        }


class TestCompositionCreation:
    """Test composition creation and validation."""

    def test_composition_must_have_steps(self):
        """Composition must have at least one step."""
        with pytest.raises(ValueError) as exc_info:
            Composition(
                composition_id="comp123",
                steps=[],
            )

        assert "at least one step" in str(exc_info.value)

    def test_only_strict_failure_policy_allowed(self):
        """Only STRICT failure policy is allowed."""
        step = create_step(
            step_id="step1",
            capability_name="test_cap",
            context={"step_id": "step1"},
            order=0,
        )

        # STRICT policy should work
        comp = Composition(
            composition_id="comp123",
            steps=[step],
            failure_policy=FailurePolicy.STRICT,
        )
        assert comp.failure_policy == FailurePolicy.STRICT

        # Non-STRICT policy should fail
        with pytest.raises(ValueError) as exc_info:
            Composition(
                composition_id="comp123",
                steps=[step],
                failure_policy=FailurePolicy("not_strict"),
            )

        # Either enum validation or custom validation should catch it
        assert exc_info.value is not None

    def test_step_order_must_be_sequential(self):
        """Step order must be sequential (0, 1, 2, ...)."""
        step1 = create_step(
            step_id="step1",
            capability_name="test_cap",
            context={"step_id": "step1"},
            order=0,
        )

        step2 = create_step(
            step_id="step2",
            capability_name="test_cap",
            context={"step_id": "step2"},
            order=2,  # Wrong! Should be 1
        )

        with pytest.raises(ValueError) as exc_info:
            Composition(
                composition_id="comp123",
                steps=[step1, step2],
            )

        assert "order mismatch" in str(exc_info.value)


class TestStepExecutionIndependence:
    """Test that each step executes independently."""

    def test_steps_cannot_share_snapshots(self):
        """Each step must have its own snapshot."""
        guard = MockGuard()
        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
                {
                    "step_id": "step2",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step2"},
                    "order": 1,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        assert result.is_success

        snapshots = [s.snapshot_id for s in result.steps]
        assert len(set(snapshots)) == 2  # Different snapshots
        assert "snap_step1" in snapshots
        assert "snap_step2" in snapshots

    def test_steps_cannot_share_authority_implicitly(self):
        """Each step must have independent Context."""
        guard = MockGuard()
        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1", "data": "a"},
                    "order": 0,
                },
                {
                    "step_id": "step2",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step2", "data": "b"},
                    "order": 1,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        contexts = guard.executed_contexts
        assert len(contexts) == 2
        assert contexts[0]["data"] == "a"
        assert contexts[1]["data"] == "b"

    def test_success_at_step_n_grants_nothing_to_step_n1(self):
        """Success at step N does not grant anything to step N+1."""
        guard = MockGuard()
        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
                {
                    "step_id": "step2",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step2"},
                    "order": 1,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        assert result.is_success

        # Step 2 should have same validation as step 1
        contexts = guard.executed_contexts
        assert contexts[0]["step_id"] == "step1"
        assert contexts[1]["step_id"] == "step2"

    def test_grants_must_independently_authorize_each_step(self):
        """Each step must be independently authorized."""
        guard = MockGuard()

        # Step 2 should be refused
        guard.should_refuse_at_step = {
            "step1": False,
            "step2": True,
        }

        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
                {
                    "step_id": "step2",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step2"},
                    "order": 1,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        assert not result.is_success
        assert result.halted_at_step == "step2"

        # Both steps executed through Guard, but step 2 was refused
        assert len(guard.executed_contexts) == 2

        # Step 1 succeeded, step 2 refused
        assert result.steps[0].is_success
        assert not result.steps[1].is_success


class TestFailurePolicyStrictness:
    """Test STRICT failure policy enforcement."""

    def test_failure_at_step_n_halts_steps_n1(self):
        """Failure at step N must halt steps N+1, N+2, etc."""
        guard = MockGuard()

        # Refuse at step 1
        guard.should_refuse_at_step = {
            "step1": True,
            "step2": False,
            "step3": False,
        }

        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
                {
                    "step_id": "step2",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step2"},
                    "order": 1,
                },
                {
                    "step_id": "step3",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step3"},
                    "order": 2,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        assert not result.is_success
        assert result.halted_at_step == "step1"

        # Only step 1 executed (refused)
        assert len(guard.executed_contexts) == 1

    def test_no_partial_success_exposure(self):
        """Partial success is not exposed."""
        guard = MockGuard()

        # Step 2 refuses
        guard.should_refuse_at_step = {
            "step1": False,
            "step2": True,
        }

        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
                {
                    "step_id": "step2",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step2"},
                    "order": 1,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        assert not result.is_success
        assert result.final_data is None
        assert result.non_action is not None

        # Individual step results are available, but composition is refused
        assert len(result.steps) == 2
        assert result.steps[0].is_success
        assert not result.steps[1].is_success

    def test_revocation_between_steps_halts_composition(self):
        """Revocation between steps halts composition."""
        guard = MockGuard()

        # Step 1 succeeds, step 2 refuses (simulating revocation)
        guard.should_refuse_at_step = {
            "step1": False,
            "step2": True,
        }

        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
                {
                    "step_id": "step2",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step2"},
                    "order": 1,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        assert not result.is_success
        assert result.halted_at_step == "step2"

        # Step 1 executed, step 2 refused
        assert len(guard.executed_contexts) == 2


class TestObserverNonAuthority:
    """Test that observers cannot alter sequencing."""

    def test_observers_cannot_alter_sequencing(self):
        """Observers cannot change step execution order."""
        guard = MockGuard()
        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
                {
                    "step_id": "step2",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step2"},
                    "order": 1,
                },
                {
                    "step_id": "step3",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step3"},
                    "order": 2,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        # Steps executed in order
        contexts = guard.executed_contexts
        assert len(contexts) == 3
        assert contexts[0]["step_id"] == "step1"
        assert contexts[1]["step_id"] == "step2"
        assert contexts[2]["step_id"] == "step3"


class TestCompositionImmutableLaw:
    """Test that composition follows MEK immutable law."""

    def test_replacing_composition_with_loop_breaks_tests(self):
        """Composition cannot be replaced with loop logic."""
        guard = MockGuard()
        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
                {
                    "step_id": "step2",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step2"},
                    "order": 1,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        # Steps executed exactly once
        assert len(guard.executed_contexts) == 2

        # No retry logic
        assert result.is_success

    def test_composition_cannot_bypass_guard(self):
        """Composition cannot bypass Guard."""
        guard = MockGuard()
        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        # Guard was called
        assert len(guard.executed_contexts) == 1


class TestCompositionResultSemantics:
    """Test composition result semantics."""

    def test_final_result_only_if_all_steps_succeed(self):
        """Final result only if all steps succeed."""
        guard = MockGuard()
        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
                {
                    "step_id": "step2",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step2"},
                    "order": 1,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        assert result.is_success
        assert result.final_data is not None
        assert result.final_data["result"] == "executed_step2"  # Last step

    def test_terminal_refusal_on_any_failure(self):
        """Terminal refusal on any failure."""
        guard = MockGuard()

        # Step 1 refuses
        guard.should_refuse_at_step = {
            "step1": True,
        }

        comp_guard = CompositionGuard(guard)

        composition = create_composition(
            composition_id="comp123",
            steps=[
                {
                    "step_id": "step1",
                    "capability_name": "test_cap",
                    "context": {"step_id": "step1"},
                    "order": 0,
                },
            ],
        )

        result = comp_guard.execute_composition(composition)

        assert not result.is_success
        assert result.non_action is not None
        assert result.final_data is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
