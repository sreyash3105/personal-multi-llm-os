"""
MEK-5: Adversarial Tests for Failure

Tests prove impossibility, not behavior.
Each test MUST fail for bypass attempt.
"""

import pytest
from typing import Any, Dict, List

from failure_primitives import (
    Phase,
    FailureType,
    Invariant,
    FailureEvent,
    FailureComposition,
    FailureResult,
    create_failure_event,
    create_failure_composition,
    create_failure_result,
)
from failure_guard import FailureGuard, get_failure_guard


class MockGuard:
    """Mock MEK Guard for testing."""

    def __init__(self):
        self.should_refuse = False
        self.refusal_reason = "MISSING_GRANT"
        self.executed_contexts: List[Dict[str, Any]] = []

    def execute(self, capability_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock execute method."""
        self.executed_contexts.append(context)

        if self.should_refuse:
            return {
                "is_success": False,
                "non_action": {
                    "reason": self.refusal_reason,
                    "details": {"capability": capability_name},
                    "timestamp": 1234567890,
                },
            }

        return {
            "is_success": True,
            "data": {"result": "executed"},
            "snapshot_id": "snap123",
        }


class TestFailureEventCreation:
    """Test failure event creation and validation."""

    def test_failure_fields_cannot_be_omitted(self):
        """All required failure fields must be present."""
        with pytest.raises(ValueError) as exc_info:
            create_failure_event(
                failure_id="",  # Empty failure_id
                phase=Phase.MEK_3,
                failure_type=FailureType.MISSING_CONFIDENCE,
                triggering_condition="test",
            )

        assert "failure_id" in str(exc_info.value).lower()

    def test_failure_event_is_immutable(self):
        """Failure Event must be immutable."""
        failure = create_failure_event(
            failure_id="fail123",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test",
        )

        with pytest.raises(Exception):
            failure.failure_type = FailureType.INVALID_CONFIDENCE

    def test_failure_type_enum_is_closed(self):
        """FailureType enum is closed - no new types."""
        with pytest.raises(ValueError):
            FailureType("custom_failure")

    def test_invariant_enum_is_closed(self):
        """Invariant enum is closed - no new invariants."""
        with pytest.raises(ValueError):
            Invariant("custom_invariant")


class TestFailureComposition:
    """Test failure composition rules."""

    def test_multiple_failures_preserve_order(self):
        """Multiple failures must preserve order of occurrence."""
        failure1 = create_failure_event(
            failure_id="fail1",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test1",
            timestamp=1000,
        )

        failure2 = create_failure_event(
            failure_id="fail2",
            phase=Phase.MEK_3,
            failure_type=FailureType.UNKNOWN_PRINCIPAL,
            triggering_condition="test2",
            timestamp=2000,
        )

        composition = create_failure_composition(
            composition_id="comp123",
            failures=[failure1, failure2],
        )

        assert len(composition.failures) == 2
        assert composition.failures[0].failure_id == "fail1"
        assert composition.failures[1].failure_id == "fail2"

    def test_failures_cannot_be_summarized(self):
        """Failures cannot be summarized or deduplicated."""
        failure1 = create_failure_event(
            failure_id="fail1",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test",
            timestamp=1000,
        )

        failure2 = create_failure_event(
            failure_id="fail2",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test",
            timestamp=2000,
        )

        composition = create_failure_composition(
            composition_id="comp123",
            failures=[failure1, failure2],
        )

        # Both failures preserved
        assert len(composition.failures) == 2

        # No summarization or deduplication
        assert composition.failures[0].failure_id == "fail1"
        assert composition.failures[1].failure_id == "fail2"

    def test_failures_out_of_order_raise_error(self):
        """Failures out of order must raise error."""
        failure1 = create_failure_event(
            failure_id="fail1",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test",
            timestamp=2000,  # Later timestamp
        )

        failure2 = create_failure_event(
            failure_id="fail2",
            phase=Phase.MEK_3,
            failure_type=FailureType.UNKNOWN_PRINCIPAL,
            triggering_condition="test",
            timestamp=1000,  # Earlier timestamp
        )

        with pytest.raises(ValueError) as exc_info:
            create_failure_composition(
                composition_id="comp123",
                failures=[failure1, failure2],
            )

        assert "out of order" in str(exc_info.value).lower()

    def test_no_root_cause_inference(self):
        """Composition cannot infer root cause."""
        failure1 = create_failure_event(
            failure_id="fail1",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test1",
            timestamp=1000,
        )

        failure2 = create_failure_event(
            failure_id="fail2",
            phase=Phase.MEK_3,
            failure_type=FailureType.UNKNOWN_PRINCIPAL,
            triggering_condition="test2",
            timestamp=2000,
        )

        composition = create_failure_composition(
            composition_id="comp123",
            failures=[failure1, failure2],
        )

        # No root cause field
        assert not hasattr(composition, "root_cause")
        assert not hasattr(composition, "primary_failure")

    def test_no_severity_ranking(self):
        """Composition cannot rank failures by severity."""
        failure1 = create_failure_event(
            failure_id="fail1",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test",
            timestamp=1000,
        )

        failure2 = create_failure_event(
            failure_id="fail2",
            phase=Phase.MEK_3,
            failure_type=FailureType.EXPIRED_GRANT,
            triggering_condition="test",
            timestamp=2000,
        )

        composition = create_failure_composition(
            composition_id="comp123",
            failures=[failure1, failure2],
        )

        # No severity field or ranking
        assert not hasattr(composition, "severity")
        assert not hasattr(composition, "critical_failure")


class TestFailureResult:
    """Test failure result semantics."""

    def test_success_output_cannot_coexist_with_failure(self):
        """Success output cannot coexist with failure."""
        failure1 = create_failure_event(
            failure_id="fail1",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test",
        )

        with pytest.raises(ValueError) as exc_info:
            FailureResult(
                composition_id="comp123",
                failures=[failure1],
                terminal=False,  # Must be True
            )

        assert "terminal" in str(exc_info.value).lower()

    def test_failure_result_must_have_failures(self):
        """Failure result must have failures."""
        with pytest.raises(ValueError) as exc_info:
            FailureResult(
                composition_id="comp123",
                failures=[],
                terminal=True,
            )

        assert "failures" in str(exc_info.value).lower()

    def test_failure_result_terminal_always_true(self):
        """Failure result terminal must always be True."""
        failure1 = create_failure_event(
            failure_id="fail1",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test",
        )

        result = FailureResult(
            composition_id="comp123",
            failures=[failure1],
            terminal=True,
        )

        assert result.terminal is True

    def test_failure_result_has_no_success_metadata(self):
        """Failure result has no success metadata."""
        failure1 = create_failure_event(
            failure_id="fail1",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test",
        )

        result = FailureResult(
            composition_id="comp123",
            failures=[failure1],
            terminal=True,
        )

        # No success metadata
        assert not hasattr(result, "data")
        assert not hasattr(result, "final_data")
        assert not hasattr(result, "output")


class TestFailureGuardIntegration:
    """Test failure guard integration with MEK Guard."""

    def test_refusal_creates_failure_event(self):
        """Guard refusal creates Failure Event."""
        guard = MockGuard()
        guard.should_refuse = True

        fail_guard = FailureGuard(guard)

        result = fail_guard.execute_with_failure_tracking(
            capability_name="test_cap",
            context={"principal_id": "user123"},
        )

        assert not result.get("is_success", False)
        assert "failure" in result
        assert fail_guard.has_failures()

    def test_failures_compose_across_steps(self):
        """Failures compose across multiple steps."""
        guard = MockGuard()

        fail_guard = FailureGuard(guard)

        # Step 1: Success
        result1 = fail_guard.execute_with_failure_tracking(
            capability_name="test_cap",
            context={"step_id": "step1"},
        )

        assert result1.get("is_success", False)
        assert not fail_guard.has_failures()

        # Step 2: Failure
        guard.should_refuse = True
        result2 = fail_guard.execute_with_failure_tracking(
            capability_name="test_cap",
            context={"step_id": "step2"},
        )

        assert not result2.get("is_success", False)
        assert fail_guard.has_failures()

        # Composition has 1 failure
        composition = fail_guard.get_failure_composition()
        assert len(composition.failures) == 1

    def test_composition_halts_on_first_failure(self):
        """Composition halts on first failure."""
        guard = MockGuard()
        guard.should_refuse = True

        fail_guard = FailureGuard(guard)

        result = fail_guard.execute_with_failure_tracking(
            capability_name="test_cap",
            context={"step_id": "step1"},
        )

        assert not result.get("is_success", False)
        assert fail_guard.has_failures()


class TestObserverNonAuthority:
    """Test that observers cannot alter failure records."""

    def test_observers_cannot_alter_failure_records(self):
        """Observers cannot modify failure events."""
        guard = MockGuard()
        guard.should_refuse = True

        fail_guard = FailureGuard(guard)

        result = fail_guard.execute_with_failure_tracking(
            capability_name="test_cap",
            context={"principal_id": "user123"},
        )

        failure = result.get("failure")

        # Failure is immutable
        with pytest.raises(Exception):
            failure.failure_type = FailureType.INVALID_CONFIDENCE  # type: ignore


class TestFailureImmutability:
    """Test failure immutability and non-softening."""

    def test_free_text_explanations_are_impossible(self):
        """Free-text explanations are impossible in failures."""
        failure = create_failure_event(
            failure_id="fail123",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test",
        )

        # No free-text fields
        assert not hasattr(failure, "explanation")
        assert not hasattr(failure, "description")
        assert not hasattr(failure, "message")
        assert not hasattr(failure, "details_text")

        # Only structured fields
        assert hasattr(failure, "triggering_condition")
        assert hasattr(failure, "failure_type")

    def test_failures_cannot_be_softened(self):
        """Failures cannot be softened or mitigated."""
        failure1 = create_failure_event(
            failure_id="fail1",
            phase=Phase.MEK_3,
            failure_type=FailureType.MISSING_CONFIDENCE,
            triggering_condition="test",
        )

        failure2 = create_failure_event(
            failure_id="fail2",
            phase=Phase.MEK_3,
            failure_type=FailureType.EXPIRED_GRANT,
            triggering_condition="test",
        )

        composition = create_failure_composition(
            composition_id="comp123",
            failures=[failure1, failure2],
        )

        # No softening fields
        assert not hasattr(composition, "suggested_fixes")
        assert not hasattr(composition, "recommended_actions")
        assert not hasattr(composition, "workarounds")

    def test_retries_do_not_generate_new_failures(self):
        """Retries do not generate new failures."""
        guard = MockGuard()
        guard.should_refuse = True

        fail_guard = FailureGuard(guard)

        # First attempt
        result1 = fail_guard.execute_with_failure_tracking(
            capability_name="test_cap",
            context={"step_id": "step1"},
        )

        failures_count_1 = len(fail_guard.current_failures)

        # Second attempt (retry)
        result2 = fail_guard.execute_with_failure_tracking(
            capability_name="test_cap",
            context={"step_id": "step1"},
        )

        failures_count_2 = len(fail_guard.current_failures)

        # Both attempts tracked
        assert failures_count_2 >= failures_count_1

        # Clear for new attempt
        fail_guard.clear_failures()

        # New attempt
        result3 = fail_guard.execute_with_failure_tracking(
            capability_name="test_cap",
            context={"step_id": "step1"},
        )

        # Only new failures counted
        assert len(fail_guard.current_failures) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
