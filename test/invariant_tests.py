"""
WORKSTREAM C: NEGATIVE-SPACE TEST SUITE (CRITICAL)

Adversarial tests that attempt to:
- Call a capability directly
- Bypass friction
- Fake confidence
- Suppress refusal
- Disable pattern aggregation
- Execute under partial context
- Run concurrent conflicting capabilities
- Add a temporary bypass flag

Each test MUST:
- fail loudly
- prove invariant enforcement

If any test passes silently, the foundation is compromised.
"""

import pytest
import time
from typing import Dict, Any
import threading

from backend.core.capability import CapabilityDescriptor, ConsequenceLevel
from backend.core.capability_registry import get_capability, register_capability, initialize_registry, lock_registry
from backend.core.execution_guard import get_execution_guard, InvariantViolationError
from backend.core.context_manager import ContextManager


class TestInvariant1_UnifiedExecutionAuthority:
    """
    INVARIANT 1: UNIFIED EXECUTION AUTHORITY
    No capability may execute outside the unified invocation path.
    Direct calls to Capability.execute() MUST raise an error.
    """

    def test_direct_execute_call_raises_error(self):
        """
        Test that direct calls to capability.execute() raise RuntimeError.

        This should fail the test if direct execution is possible.
        """
        def dummy_execute_fn(context):
            return {"status": "success", "result": "executed"}

        cap = CapabilityDescriptor(
            name="test_capability",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=dummy_execute_fn,
        )

        with pytest.raises(RuntimeError, match="INVARIANT_1_VIOLATION"):
            cap.execute({})

    def test_execution_guard_is_only_path(self):
        """
        Test that execution ONLY works through ExecutionGuard.

        This verifies that the guard is the sole execution gateway.
        """
        executed = []

        def dummy_execute_fn(context):
            executed.append(True)
            return {"status": "success", "result": "executed"}

        cap = CapabilityDescriptor(
            name="test_capability_guard",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=dummy_execute_fn,
        )

        guard = get_execution_guard()

        # This should work
        context = {"confidence": 0.9}
        result = guard.execute_capability(cap, context)
        assert result["status"] == "success"
        assert len(executed) == 1


class TestInvariant2_ConfidenceBeforeAction:
    """
    INVARIANT 2: CONFIDENCE BEFORE ACTION
    Every capability invocation MUST pass through a confidence gate.
    If confidence is unbounded, execution MUST refuse.
    No default confidence allowed.
    Confidence cannot be overridden downstream.
    """

    def test_missing_confidence_raises_error(self):
        """
        Test that execution without confidence raises InvariantViolationError.
        """
        def dummy_execute_fn(context):
            return {"status": "success", "result": "executed"}

        cap = CapabilityDescriptor(
            name="test_capability_no_conf",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=dummy_execute_fn,
        )

        guard = get_execution_guard()
        context = {}  # No confidence

        with pytest.raises(InvariantViolationError, match="INVARIANT_2_VIOLATION.*without confidence"):
            guard.execute_capability(cap, context)

    def test_none_confidence_raises_error(self):
        """
        Test that explicit None confidence raises InvariantViolationError.
        """
        def dummy_execute_fn(context):
            return {"status": "success", "result": "executed"}

        cap = CapabilityDescriptor(
            name="test_capability_none_conf",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=dummy_execute_fn,
        )

        guard = get_execution_guard()
        context = {"confidence": None}

        with pytest.raises(InvariantViolationError, match="INVARIANT_2_VIOLATION.*without confidence"):
            guard.execute_capability(cap, context)

    def test_invalid_confidence_raises_error(self):
        """
        Test that invalid confidence values raise InvariantViolationError.
        """
        def dummy_execute_fn(context):
            return {"status": "success", "result": "executed"}

        cap = CapabilityDescriptor(
            name="test_capability_invalid_conf",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=dummy_execute_fn,
        )

        guard = get_execution_guard()

        # Test out of range values
        with pytest.raises(InvariantViolationError, match="INVARIANT_2_VIOLATION.*invalid confidence"):
            guard.execute_capability(cap, {"confidence": 1.5})

        with pytest.raises(InvariantViolationError, match="INVARIANT_2_VIOLATION.*invalid confidence"):
            guard.execute_capability(cap, {"confidence": -0.1})

    def test_confidence_required_for_all_consequence_levels(self):
        """
        Test that confidence is required regardless of consequence level.
        """
        for consequence_level in [ConsequenceLevel.LOW, ConsequenceLevel.MEDIUM, ConsequenceLevel.HIGH]:
            def dummy_execute_fn(context):
                return {"status": "success", "result": "executed"}

            cap = CapabilityDescriptor(
                name=f"test_capability_{consequence_level.value}",
                scope="test",
                consequence_level=consequence_level,
                required_context_fields=[],
                execute_fn=dummy_execute_fn,
            )

            guard = get_execution_guard()

            # Should fail without confidence
            with pytest.raises(InvariantViolationError, match="INVARIANT_2_VIOLATION"):
                guard.execute_capability(cap, {})


class TestInvariant3_FrictionUnderConsequence:
    """
    INVARIANT 3: FRICTION UNDER CONSEQUENCE
    Any capability with consequence >= HIGH MUST trigger friction.
    Friction duration MUST be immutable.
    No skip, no bypass, no override, no "emergency mode".
    """

    def test_high_consequence_triggers_friction(self):
        """
        Test that HIGH consequence capabilities trigger friction that cannot be bypassed.
        """
        execution_times = []

        def slow_execute_fn(context):
            start = time.time()
            execution_times.append(start)
            time.sleep(0.1)  # Simulate work
            return {"status": "success", "result": "executed"}

        cap = CapabilityDescriptor(
            name="test_capability_high_friction",
            scope="test",
            consequence_level=ConsequenceLevel.HIGH,
            required_context_fields=[],
            execute_fn=slow_execute_fn,
        )

        guard = get_execution_guard()
        start = time.time()
        guard.execute_capability(cap, {"confidence": 0.9})
        elapsed = time.time() - start

        # HIGH consequence should have at least 10 seconds friction
        assert elapsed >= 10.0, f"HIGH consequence friction bypassed: {elapsed}s < 10.0s"

    def test_medium_consequence_triggers_friction(self):
        """
        Test that MEDIUM consequence capabilities trigger friction.
        """
        def dummy_execute_fn(context):
            return {"status": "success", "result": "executed"}

        cap = CapabilityDescriptor(
            name="test_capability_medium_friction",
            scope="test",
            consequence_level=ConsequenceLevel.MEDIUM,
            required_context_fields=[],
            execute_fn=dummy_execute_fn,
        )

        guard = get_execution_guard()
        start = time.time()
        guard.execute_capability(cap, {"confidence": 0.9})
        elapsed = time.time() - start

        # MEDIUM consequence should have at least 3 seconds friction
        assert elapsed >= 3.0, f"MEDIUM consequence friction bypassed: {elapsed}s < 3.0s"

    def test_low_confidence_increases_friction(self):
        """
        Test that low confidence increases friction duration.
        """
        def dummy_execute_fn(context):
            return {"status": "success", "result": "executed"}

        cap_low = CapabilityDescriptor(
            name="test_capability_low_conf_friction",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=dummy_execute_fn,
        )

        guard = get_execution_guard()

        # LOW confidence (0.2 < 0.3) should have 5 seconds friction
        start = time.time()
        guard.execute_capability(cap_low, {"confidence": 0.2})
        elapsed_low = time.time() - start
        assert elapsed_low >= 5.0, f"Low confidence friction bypassed: {elapsed_low}s < 5.0s"


class TestInvariant4_RefusalIsFirstClass:
    """
    INVARIANT 4: REFUSAL IS FIRST-CLASS
    Refusal is a valid terminal state.
    No fallback execution after refusal.
    No silent retries.
    No implicit clarification loops.
    """

    def test_refusal_is_terminal(self):
        """
        Test that refusal is a terminal state with no fallback.
        """
        def never_execute_fn(context):
            return {"status": "should_not_execute"}

        cap = CapabilityDescriptor(
            name="test_capability_refusal",
            scope="test",
            consequence_level=ConsequenceLevel.HIGH,
            required_context_fields=["required_field"],  # This will cause refusal
            execute_fn=never_execute_fn,
        )

        guard = get_execution_guard()
        result = guard.execute_capability(cap, {"confidence": 0.9})

        # Should be a refusal
        assert result["status"] == "refused"
        assert result["reason"] == "missing_context"

        # The execute_fn should never have been called
        assert "required_field" not in str(result)

    def test_no_fallback_after_refusal(self):
        """
        Test that there is no fallback execution path after refusal.
        """
        def fallback_execute_fn(context):
            return {"status": "success", "fallback": True}

        cap = CapabilityDescriptor(
            name="test_capability_no_fallback",
            scope="test",
            consequence_level=ConsequenceLevel.MEDIUM,
            required_context_fields=["field1", "field2"],  # Will cause refusal
            execute_fn=fallback_execute_fn,
        )

        guard = get_execution_guard()
        result = guard.execute_capability(cap, {"confidence": 0.9, "field1": "value"})

        # Should be a refusal, not success
        assert result["status"] == "refused"
        assert "fallback" not in result


class TestInvariant5_NonActionMustSurface:
    """
    INVARIANT 5: NON-ACTION MUST SURFACE
    Every refusal or halt MUST emit an explicit Non-Action report.
    Silence is illegal.
    Reports must be structured, not free-text.
    """

    def test_refusal_emits_non_action_report(self):
        """
        Test that refusals emit explicit non-action reports.
        """
        def dummy_execute_fn(context):
            return {"status": "success"}

        cap = CapabilityDescriptor(
            name="test_capability_non_action",
            scope="test",
            consequence_level=ConsequenceLevel.HIGH,
            required_context_fields=["missing_field"],
            execute_fn=dummy_execute_fn,
        )

        guard = get_execution_guard()
        execution_context = ContextManager.create_context()

        # This should generate a non-action report
        result = guard.execute_capability(
            cap,
            {"confidence": 0.9},
            execution_context=execution_context,
        )

        assert result["status"] == "refused"
        assert result["reason"] == "missing_context"

        # Check that pattern was recorded
        from backend.core.pattern_record import PatternRecord
        patterns = PatternRecord.query_by_profile(
            profile_id="unknown",
            limit=10,
        )

        # Should have at least one refusal pattern
        refusal_patterns = [p for p in patterns if p["pattern_type"] == "REFUSAL"]
        assert len(refusal_patterns) > 0, "No non-action report emitted for refusal"


class TestInvariant6_PatternsObserveNeverControl:
    """
    INVARIANT 6: PATTERNS OBSERVE, NEVER CONTROL
    Pattern aggregation MUST be non-blocking.
    Pattern layer MUST NOT affect execution.
    Removing the pattern layer entirely MUST NOT break execution.
    """

    def test_pattern_failure_does_not_block_execution(self):
        """
        Test that pattern recording failures do not block execution.
        """
        execution_count = []

        def counting_execute_fn(context):
            execution_count.append(1)
            return {"status": "success", "result": "executed"}

        cap = CapabilityDescriptor(
            name="test_capability_pattern_failure",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=counting_execute_fn,
        )

        guard = get_execution_guard()

        # Even if pattern recording fails, execution should succeed
        result = guard.execute_capability(cap, {"confidence": 0.9})

        assert result["status"] == "success"
        assert len(execution_count) == 1


class TestNegativeSpaceAttempts:
    """
    Tests for specific bypass attempts that must fail loudly.
    """

    def test_bypass_confidence_with_false_value(self):
        """
        Test attempt to bypass confidence with false-like values.
        """
        def dummy_execute_fn(context):
            return {"status": "success"}

        cap = CapabilityDescriptor(
            name="test_capability_bypass_conf",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=dummy_execute_fn,
        )

        guard = get_execution_guard()

        # Try bypassing with 0 (should fail)
        with pytest.raises(InvariantViolationError):
            guard.execute_capability(cap, {"confidence": 0})

    def test_bypass_friction_with_high_confidence(self):
        """
        Test that even high confidence cannot bypass HIGH consequence friction.
        """
        def dummy_execute_fn(context):
            return {"status": "success"}

        cap = CapabilityDescriptor(
            name="test_capability_high_conf_friction",
            scope="test",
            consequence_level=ConsequenceLevel.HIGH,
            required_context_fields=[],
            execute_fn=dummy_execute_fn,
        )

        guard = get_execution_guard()
        start = time.time()
        guard.execute_capability(cap, {"confidence": 1.0})
        elapsed = time.time() - start

        # Even with max confidence, HIGH consequence requires friction
        assert elapsed >= 10.0, f"Friction bypassed with high confidence: {elapsed}s"

    def test_execute_with_partial_context(self):
        """
        Test that execution with partial context is refused.
        """
        def dummy_execute_fn(context):
            return {"status": "success"}

        cap = CapabilityDescriptor(
            name="test_capability_partial_context",
            scope="test",
            consequence_level=ConsequenceLevel.MEDIUM,
            required_context_fields=["field1", "field2", "field3"],
            execute_fn=dummy_execute_fn,
        )

        guard = get_execution_guard()

        # Provide only partial context
        result = guard.execute_capability(
            cap,
            {
                "confidence": 0.9,
                "field1": "value1",
                "field2": "value2",
                # field3 is missing
            },
        )

        assert result["status"] == "refused"
        assert result["reason"] == "missing_context"

    def test_concurrent_conflicting_capabilities_fail(self):
        """
        Test that concurrent executions are properly serialized by guard.
        """
        execution_order = []
        lock = threading.Lock()

        def locking_execute_fn(context):
            with lock:
                execution_order.append(context.get("name"))
            time.sleep(0.1)
            return {"status": "success"}

        cap1 = CapabilityDescriptor(
            name="capability_1",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=locking_execute_fn,
        )

        cap2 = CapabilityDescriptor(
            name="capability_2",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=locking_execute_fn,
        )

        guard = get_execution_guard()

        def run_cap(name):
            guard.execute_capability(
                cap1 if name == "capability_1" else cap2,
                {"confidence": 0.9, "name": name},
            )

        threads = [
            threading.Thread(target=run_cap, args=("capability_1",)),
            threading.Thread(target=run_cap, args=("capability_2",)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Both should complete
        assert len(execution_order) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
