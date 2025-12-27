"""
Negative capability enforcement tests.

Tests for INVARIANT 7: NO AUTONOMY, EVER
"""

import pytest
from backend.core.negative_capability import (
    ProhibitedBehaviorError,
    block_learning,
    block_adaptive_thresholds,
    block_retry_loops,
    block_urgency_shortcuts,
    block_optimization,
    block_escalation,
    NegativeCapabilityEnforcer,
    no_learning,
    no_adaptation,
    no_retry,
    no_escalation,
)


class TestNegativeCapabilityEnforcement:
    """
    Tests that negative capabilities are enforced at runtime.
    """

    def test_block_learning_decorator(self):
        """
        Test that learning is blocked by decorator.
        """
        @block_learning(reason="Test learning is prohibited")
        def attempt_learning():
            return "should not execute"

        with pytest.raises(ProhibitedBehaviorError, match="LEARNING_PROHIBITED"):
            attempt_learning()

    def test_block_adaptive_thresholds_decorator(self):
        """
        Test that adaptive thresholds are blocked by decorator.
        """
        @block_adaptive_thresholds(reason="Test adaptation is prohibited")
        def attempt_adaptation():
            return "should not execute"

        with pytest.raises(ProhibitedBehaviorError, match="ADAPTIVE_THRESHOLDS_PROHIBITED"):
            attempt_adaptation()

    def test_block_retry_loops_decorator(self):
        """
        Test that retry loops are blocked by decorator.
        """
        @block_retry_loops(reason="Test retry is prohibited")
        def attempt_retry():
            return "should not execute"

        with pytest.raises(ProhibitedBehaviorError, match="RETRY_LOOPS_PROHIBITED"):
            attempt_retry()

    def test_block_urgency_shortcuts_decorator(self):
        """
        Test that urgency shortcuts are blocked by decorator.
        """
        @block_urgency_shortcuts(reason="Test urgency is prohibited")
        def attempt_urgency_shortcut():
            return "should not execute"

        with pytest.raises(ProhibitedBehaviorError, match="URGENCY_SHORTCUTS_PROHIBITED"):
            attempt_urgency_shortcut()

    def test_block_optimization_decorator(self):
        """
        Test that optimization is blocked by decorator.
        """
        @block_optimization(reason="Test optimization is prohibited")
        def attempt_optimization():
            return "should not execute"

        with pytest.raises(ProhibitedBehaviorError, match="OPTIMIZATION_PROHIBITED"):
            attempt_optimization()

    def test_block_escalation_decorator(self):
        """
        Test that escalation is blocked by decorator.
        """
        @block_escalation(reason="Test escalation is prohibited")
        def attempt_escalation():
            return "should not execute"

        with pytest.raises(ProhibitedBehaviorError, match="AUTONOMOUS_ESCALATION_PROHIBITED"):
            attempt_escalation()

    def test_check_for_prohibited_patterns(self):
        """
        Test that prohibited patterns are detected.
        """
        with pytest.raises(ProhibitedBehaviorError, match="PROHIBITED_PATTERN_DETECTED"):
            NegativeCapabilityEnforcer.check_for_prohibited_patterns(
                "This system will learn from your interactions"
            )

    def test_enforce_no_learning(self):
        """
        Test that learning attempts are blocked.
        """
        with pytest.raises(ProhibitedBehaviorError, match="LEARNING_ATTEMPT_DETECTED"):
            NegativeCapabilityEnforcer.enforce_no_learning(
                "We will update the model based on this"
            )

    def test_enforce_no_adaptation(self):
        """
        Test that adaptation attempts are blocked.
        """
        with pytest.raises(ProhibitedBehaviorError, match="ADAPTATION_ATTEMPT_DETECTED"):
            NegativeCapabilityEnforcer.enforce_no_adaptation(
                "We will adjust the threshold based on usage"
            )

    def test_enforce_no_autonomous_action(self):
        """
        Test that autonomous action attempts are blocked.
        """
        with pytest.raises(ProhibitedBehaviorError, match="AUTONOMOUS_ACTION_ATTEMPT_DETECTED"):
            NegativeCapabilityEnforcer.enforce_no_autonomous_action(
                "System will automatically approve this request"
            )


class TestConvenienceDecorators:
    """
    Tests for convenience decorators.
    """

    def test_no_learning_decorator(self):
        """
        Test that @no_learning decorator blocks learning.
        """
        @no_learning
        def function_that_should_not_learn():
            return "executed"

        with pytest.raises(ProhibitedBehaviorError):
            function_that_should_not_learn()

    def test_no_adaptation_decorator(self):
        """
        Test that @no_adaptation decorator blocks adaptation.
        """
        @no_adaptation
        def function_that_should_not_adapt():
            return "executed"

        with pytest.raises(ProhibitedBehaviorError):
            function_that_should_not_adapt()

    def test_no_retry_decorator(self):
        """
        Test that @no_retry decorator blocks automatic retries.
        """
        @no_retry
        def function_that_should_not_retry():
            return "executed"

        with pytest.raises(ProhibitedBehaviorError):
            function_that_should_not_retry()

    def test_no_escalation_decorator(self):
        """
        Test that @no_escalation decorator blocks autonomous escalation.
        """
        @no_escalation
        def function_that_should_not_escalate():
            return "executed"

        with pytest.raises(ProhibitedBehaviorError):
            function_that_should_not_escalate()


class TestEscalationBlocking:
    """
    Tests specific to blocking escalation behavior.
    """

    def test_escalation_based_on_confidence_is_blocked(self):
        """
        Test that automatic escalation based on low confidence is blocked.
        """
        from backend.core.local_runner import LocalRunner

        runner = LocalRunner()

        # This should raise ProhibitedBehaviorError
        with pytest.raises(ProhibitedBehaviorError, match="INVARIANT_7_VIOLATION.*Autonomous escalation"):
            runner.should_escalate({
                "confidence_score": 0.5,
                "conflict_score": 0.2,
            })

    def test_inject_escalation_comment_is_blocked(self):
        """
        Test that automatic escalation comment injection is blocked.
        """
        from backend.core.local_runner import LocalRunner

        runner = LocalRunner()

        # This should raise ProhibitedBehaviorError
        with pytest.raises(ProhibitedBehaviorError, match="INVARIANT_7_VIOLATION.*Autonomous escalation"):
            runner.inject_escalation_comment(
                "some code here",
                "low confidence detected"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
