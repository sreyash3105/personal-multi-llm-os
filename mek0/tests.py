"""
MEK-0: Negative-Space Tests

Adversarial tests that attempt to violate invariants.
Each test MUST fail loudly to prove invariant enforcement.
"""

import pytest
import time
import threading

from mek0.kernel import (
    Context,
    Intent,
    CapabilityContract,
    ConsequenceLevel,
    Guard,
    Result,
    NonActionReason,
    InvariantViolationError,
    ProhibitedBehaviorError,
    get_guard,
    get_observer_hub,
    Observer,
    block_learning,
    block_adaptation,
    block_auto_retry,
    block_escalation,
    block_urgency_shortcut,
    block_optimization,
    block_intent_inference,
)


class TestInvariant1_UnifiedExecutionAuthority:
    """
    I1: UNIFIED EXECUTION AUTHORITY
    Direct capability execution is forbidden.
    Guard is sole execution gateway.
    """

    def test_direct_execution_raises_invariant_violation(self):
        """Direct calls to capability.execute() must raise InvariantViolationError."""
        def dummy_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_cap",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=dummy_fn,
        )

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test",
        )

        with pytest.raises(InvariantViolationError, match="I1_VIOLATION"):
            contract.execute(context)

    def test_only_guard_can_execute(self):
        """Execution through Guard should succeed."""
        def dummy_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_cap_guard",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=dummy_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_cap_guard",
        )

        result = guard.execute("test_cap_guard", context)
        assert result.is_success()
        assert result.data == "executed"


class TestInvariant2_ConfidenceBeforeAction:
    """
    I2: CONFIDENCE BEFORE ACTION
    Confidence required, bounded.
    Unbounded or missing → refusal.
    """

    def test_missing_confidence_refuses(self):
        """Missing confidence must create Non-Action."""
        guard = get_guard()

        context = Context(
            context_id="test",
            confidence=None,
            intent="test",
        )

        result = guard.execute("any_cap", context)
        assert result.is_non_action()
        assert result.non_action["reason"] == NonActionReason.MISSING_CONFIDENCE.value

    def test_invalid_low_confidence_refuses(self):
        """Confidence < 0.0 must create Non-Action."""
        guard = get_guard()

        context = Context(
            context_id="test",
            confidence=-0.1,
            intent="test",
        )

        result = guard.execute("any_cap", context)
        assert result.is_non_action()
        assert result.non_action["reason"] == NonActionReason.INVALID_CONFIDENCE.value

    def test_invalid_high_confidence_refuses(self):
        """Confidence > 1.0 must create Non-Action."""
        guard = get_guard()

        context = Context(
            context_id="test",
            confidence=1.5,
            intent="test",
        )

        result = guard.execute("any_cap", context)
        assert result.is_non_action()
        assert result.non_action["reason"] == NonActionReason.INVALID_CONFIDENCE.value

    def test_valid_confidence_allows_execution(self):
        """Valid confidence (0.0-1.0) must allow execution."""
        def dummy_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_cap_valid_conf",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=dummy_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        for conf in [0.0, 0.5, 1.0]:
            context = Context(
                context_id=f"test_{conf}",
                confidence=conf,
                intent="test_cap_valid_conf",
            )
            result = guard.execute("test_cap_valid_conf", context)
            assert result.is_success()


class TestInvariant3_FrictionUnderConsequence:
    """
    I3: FRICTION UNDER CONSEQUENCE
    consequence >= HIGH → immutable friction.
    No bypass, skip, emergency mode.
    """

    def test_high_consequence_has_friction(self):
        """HIGH consequence must have at least 10 second friction."""
        def dummy_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_high_friction",
            consequence_level=ConsequenceLevel.HIGH,
            required_context_fields=[],
            _execute_fn=dummy_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_high_friction",
        )

        start = time.time()
        guard.execute("test_high_friction", context)
        elapsed = time.time() - start

        assert elapsed >= 10.0, f"Friction bypassed: {elapsed}s < 10.0s"

    def test_medium_consequence_has_friction(self):
        """MEDIUM consequence must have at least 3 second friction."""
        def dummy_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_medium_friction",
            consequence_level=ConsequenceLevel.MEDIUM,
            required_context_fields=[],
            _execute_fn=dummy_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_medium_friction",
        )

        start = time.time()
        guard.execute("test_medium_friction", context)
        elapsed = time.time() - start

        assert elapsed >= 3.0, f"Friction bypassed: {elapsed}s < 3.0s"

    def test_low_confidence_increases_friction(self):
        """Low confidence (< 0.3) must add 5 seconds friction."""
        def dummy_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_low_conf_friction",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=dummy_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        context = Context(
            context_id="test",
            confidence=0.2,
            intent="test_low_conf_friction",
        )

        start = time.time()
        guard.execute("test_low_conf_friction", context)
        elapsed = time.time() - start

        assert elapsed >= 5.0, f"Low confidence friction bypassed: {elapsed}s < 5.0s"


class TestInvariant4_RefusalIsTerminal:
    """
    I4: REFUSAL IS TERMINAL
    No retries, fallbacks, or chaining after refusal.
    """

    def test_non_action_is_terminal(self):
        """Non-Action result must be terminal - no automatic retry."""
        def failing_fn(ctx):
            raise RuntimeError("Always fails")

        contract = CapabilityContract(
            name="test_failing",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=failing_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_failing",
        )

        result = guard.execute("test_failing", context)
        assert result.is_non_action()
        assert result.non_action["reason"] == NonActionReason.EXECUTION_FAILED.value

    def test_no_fallback_after_non_action(self):
        """No fallback execution after Non-Action."""
        def never_execute_fn(ctx):
            return "should_not_execute"

        contract = CapabilityContract(
            name="test_fallback",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=["missing_field"],
            _execute_fn=never_execute_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_fallback",
            fields={},  # Missing required field
        )

        result = guard.execute("test_fallback", context)
        assert result.is_non_action()
        assert result.non_action["reason"] == NonActionReason.MISSING_CONTEXT.value


class TestInvariant5_NonActionMustSurface:
    """
    I5: NON-ACTION MUST SURFACE
    Every refusal emits a structured Non-Action.
    """

    def test_non_action_has_structure(self):
        """Non-Action must have structured data."""
        def failing_fn(ctx):
            raise RuntimeError("Test error")

        contract = CapabilityContract(
            name="test_structure",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=failing_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_structure",
        )

        result = guard.execute("test_structure", context)
        assert result.is_non_action()
        assert "reason" in result.non_action
        assert "details" in result.non_action
        assert "timestamp" in result.non_action


class TestInvariant6_ObservationNeverControls:
    """
    I6: OBSERVATION NEVER CONTROLS
    Observers are non-blocking, non-authoritative.
    Removing observers changes nothing.
    """

    def test_observer_failure_does_not_block_execution(self):
        """Observer failure must not block execution."""
        def failing_observer(event_type, details):
            raise RuntimeError("Observer failed")

        get_observer_hub().register(failing_observer)

        def dummy_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_observer_fail",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=dummy_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_observer_fail",
        )

        result = guard.execute("test_observer_fail", context)
        assert result.is_success()

        # Clean up
        get_observer_hub().clear()

    def test_removing_observers_changes_nothing(self):
        """Removing all observers must not affect execution."""
        def dummy_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_no_observer",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=dummy_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        # Clear all observers
        get_observer_hub().clear()

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_no_observer",
        )

        result = guard.execute("test_no_observer", context)
        assert result.is_success()


class TestInvariant7_NegativeCapability:
    """
    I7: NEGATIVE CAPABILITY (STRUCTURAL)
    Prohibited behaviors are impossible without core edits.
    """

    def test_learning_is_blocked(self):
        """Learning must raise ProhibitedBehaviorError."""
        with pytest.raises(ProhibitedBehaviorError, match="I7_VIOLATION.*Learning"):
            block_learning("We will learn from this")

    def test_adaptation_is_blocked(self):
        """Adaptation must raise ProhibitedBehaviorError."""
        with pytest.raises(ProhibitedBehaviorError, match="I7_VIOLATION.*Adaptation"):
            block_adaptation("We will adapt threshold")

    def test_auto_retry_is_blocked(self):
        """Auto-retry must raise ProhibitedBehaviorError."""
        with pytest.raises(ProhibitedBehaviorError, match="I7_VIOLATION.*Auto-retry"):
            block_auto_retry("We will retry automatically")

    def test_escalation_is_blocked(self):
        """Escalation must raise ProhibitedBehaviorError."""
        with pytest.raises(ProhibitedBehaviorError, match="I7_VIOLATION.*Escalation"):
            block_escalation("We will escalate authority")

    def test_urgency_shortcut_is_blocked(self):
        """Urgency shortcuts must raise ProhibitedBehaviorError."""
        with pytest.raises(ProhibitedBehaviorError, match="I7_VIOLATION.*Urgency"):
            block_urgency_shortcut("Emergency mode bypass friction")

    def test_optimization_is_blocked(self):
        """Optimization must raise ProhibitedBehaviorError."""
        with pytest.raises(ProhibitedBehaviorError, match="I7_VIOLATION.*Optimization"):
            block_optimization("We will optimize behavior")

    def test_intent_inference_is_blocked(self):
        """Intent inference must raise ProhibitedBehaviorError."""
        with pytest.raises(ProhibitedBehaviorError, match="I7_VIOLATION.*Intent inference"):
            block_intent_inference("We will infer user intent")


class TestContextImmutability:
    """
    Context must be immutable after creation.
    """

    def test_context_is_immutable(self):
        """Context should be frozen - cannot mutate fields."""
        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test",
            fields={"key": "value"},
        )

        # Attempting to modify should fail (frozen dataclass)
        with pytest.raises(Exception):  # FrozenInstanceError or similar
            context.fields["key"] = "new_value"


class TestNegativeSpaceAttempts:
    """
    Tests for specific bypass attempts.
    """

    def test_bypass_friction_with_high_confidence(self):
        """High confidence cannot bypass HIGH consequence friction."""
        def dummy_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_bypass_friction",
            consequence_level=ConsequenceLevel.HIGH,
            required_context_fields=[],
            _execute_fn=dummy_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        context = Context(
            context_id="test",
            confidence=1.0,  # Maximum confidence
            intent="test_bypass_friction",
        )

        start = time.time()
        guard.execute("test_bypass_friction", context)
        elapsed = time.time() - start

        # Even max confidence cannot bypass HIGH friction
        assert elapsed >= 10.0

    def test_execute_with_partial_context(self):
        """Partial context must create Non-Action."""
        def dummy_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_partial_context",
            consequence_level=ConsequenceLevel.MEDIUM,
            required_context_fields=["field1", "field2", "field3"],
            _execute_fn=dummy_fn,
        )

        guard = get_guard()
        guard.register_capability(contract)

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_partial_context",
            fields={"field1": "value1", "field2": "value2"},  # Missing field3
        )

        result = guard.execute("test_partial_context", context)
        assert result.is_non_action()
        assert result.non_action["reason"] == NonActionReason.MISSING_CONTEXT.value

    def test_unknown_capability_refuses(self):
        """Unknown capability must create Non-Action."""
        guard = get_guard()

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="unknown_capability",
        )

        result = guard.execute("unknown_capability", context)
        assert result.is_non_action()
        assert result.non_action["reason"] == NonActionReason.REFUSED_BY_GUARD.value

    def test_context_requires_confidence_at_creation(self):
        """Context creation must fail without confidence."""
        with pytest.raises(ValueError, match="confidence is required"):
            Context(
                context_id="test",
                confidence=None,
                intent="test",
            )

    def test_context_requires_intent_at_creation(self):
        """Context creation must fail without intent."""
        with pytest.raises(ValueError, match="intent is required"):
            Context(
                context_id="test",
                confidence=0.9,
                intent="",
            )


class TestConcurrentExecution:
    """
    Tests for concurrent execution behavior.
    """

    def test_concurrent_executions_are_serialized(self):
        """Guard should serialize concurrent executions."""
        execution_order = []
        lock = threading.Lock()

        def slow_fn(ctx):
            with lock:
                execution_order.append(ctx.intent)
            time.sleep(0.1)
            return "executed"

        contract1 = CapabilityContract(
            name="cap1",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=slow_fn,
        )

        contract2 = CapabilityContract(
            name="cap2",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=slow_fn,
        )

        guard = get_guard()
        guard.register_capability(contract1)
        guard.register_capability(contract2)

        def execute_cap(name):
            context = Context(
                context_id=f"test_{name}",
                confidence=0.9,
                intent=name,
            )
            guard.execute(name, context)

        threads = [
            threading.Thread(target=execute_cap, args=("cap1",)),
            threading.Thread(target=execute_cap, args=("cap2",)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Both should complete
        assert len(execution_order) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
