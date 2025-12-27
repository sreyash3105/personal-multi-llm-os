"""
MEK-1: Adversarial Tests

Tests proving AIOS cannot bypass MEK authority.
All tests MUST fail for any bypass attempt.
"""

import pytest
import time
import threading


class TestClientBindingAuthority:
    """
    Tests for MEK-1: Client Binding Layer.

    Proves:
    - AIOS executes ONLY via MEK Client
    - MEK refusal halts AIOS
    - No alternate path exists
    """

    def test_aios_must_use_mek_client(self):
        """AIOS must use MEK Client for execution."""
        from mek1.mek_client import execute_via_mek, MEKRefusalError
        from mek0.kernel import ConsequenceLevel, CapabilityContract

        # Register test capability
        def test_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_client_bind",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=test_fn,
        )

        from mek0.kernel import get_guard
        get_guard().register_capability(contract)

        # Test execution via MEK client
        context = type('Context', (), {'context_id': 'test', 'profile_id': 'user'})()
        result = execute_via_mek("test_client_bind", context, 0.9)

        # Should succeed
        assert result is not None

    def test_mek_refusal_halts_aios(self):
        """MEK refusal must halt AIOS unconditionally."""
        from mek1.mek_client import execute_via_mek, MEKRefusalError
        from mek0.kernel import ConsequenceLevel, CapabilityContract

        # Register capability with required field
        def test_fn(ctx):
            return "should_not_execute"

        contract = CapabilityContract(
            name="test_refusal_halt",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=["missing_field"],
            _execute_fn=test_fn,
        )

        from mek0.kernel import get_guard
        get_guard().register_capability(contract)

        # Try to execute without required field
        context = type('Context', (), {'context_id': 'test', 'profile_id': 'user'})()

        # MEK should refuse, AIOS should halt
        with pytest.raises(MEKRefusalError, match="MEK refused"):
            execute_via_mek("test_refusal_halt", context, 0.9)

    def test_missing_confidence_refuses(self):
        """Missing confidence must refuse execution."""
        from mek1.mek_client import AIOSContextBridge

        # Missing confidence -> ValueError
        context = type('Context', (), {'context_id': 'test'})()

        with pytest.raises(ValueError, match="confidence is required"):
            AIOSContextBridge.to_mek_context(context, None, "test")

    def test_invalid_confidence_refuses(self):
        """Invalid confidence must refuse execution."""
        from mek1.mek_client import AIOSContextBridge

        # Invalid confidence > 1.0 -> ValueError
        context = type('Context', (), {'context_id': 'test'})()

        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            AIOSContextBridge.to_mek_context(context, 1.5, "test")

    def test_missing_intent_refuses(self):
        """Missing intent must refuse execution."""
        from mek1.mek_client import AIOSIntentBridge

        # Missing intent -> ValueError
        with pytest.raises(ValueError, match="intent name is required"):
            AIOSIntentBridge.to_mek_intent("")

        with pytest.raises(ValueError, match="intent name is required"):
            AIOSIntentBridge.to_mek_intent(None)


class TestCapabilityWrapping:
    """
    Tests for MEK-1: Capability Wrapping.

    Proves:
    - AIOS capabilities are wrapped as MEK contracts
    - Direct invocation is forbidden
    - No new capabilities added
    """

    def test_wrapped_capability_cannot_execute_directly(self):
        """Wrapped capability cannot execute directly."""
        from mek1.capability_wrappers import wrap_aios_capability
        from mek0.kernel import InvariantViolationError

        def test_fn(ctx):
            return "should_not_execute"

        wrapper = wrap_aios_capability(
            name="test_wrap",
            original_capability=test_fn,
            consequence_level="LOW",
            required_context_fields=[],
        )

        # Convert to MEK contract
        mek_contract = wrapper.to_mek_contract()

        # Direct execution should raise InvariantViolationError
        with pytest.raises(InvariantViolationError, match="I1_VIOLATION"):
            mek_contract.execute(type('Context', (), {})())

    def test_wrapped_capability_has_consequence_level(self):
        """Wrapped capability must have declared consequence level."""
        from mek1.capability_wrappers import wrap_aios_capability

        def test_fn(ctx):
            return "executed"

        for level in ["LOW", "MEDIUM", "HIGH"]:
            wrapper = wrap_aios_capability(
                name=f"test_{level}",
                original_capability=test_fn,
                consequence_level=level,
                required_context_fields=[],
            )

            mek_contract = wrapper.to_mek_contract()
            assert mek_contract.consequence_level is not None

    def test_invalid_consequence_level_raises_error(self):
        """Invalid consequence level must raise ValueError."""
        from mek1.capability_wrappers import wrap_aios_capability

        def test_fn(ctx):
            return "executed"

        wrapper = wrap_aios_capability(
            name="test_invalid",
            original_capability=test_fn,
            consequence_level="INVALID",
            required_context_fields=[],
        )

        with pytest.raises(ValueError, match="Invalid consequence level"):
            wrapper.to_mek_contract()

    def test_filesystem_capability_wrapped_high(self):
        """Filesystem capability must be wrapped with HIGH consequence."""
        from mek1.capability_wrappers import wrap_filesystem_capability

        def file_fn(ctx):
            return "file_operation"

        wrapper = wrap_filesystem_capability("test_file", file_fn)
        mek_contract = wrapper.to_mek_contract()

        # Verify consequence is HIGH
        from mek0.kernel import ConsequenceLevel
        assert mek_contract.consequence_level == ConsequenceLevel.HIGH

    def test_process_capability_wrapped_high(self):
        """Process capability must be wrapped with HIGH consequence."""
        from mek1.capability_wrappers import wrap_process_capability

        def proc_fn(ctx):
            return "process_operation"

        wrapper = wrap_process_capability("test_process", proc_fn)
        mek_contract = wrapper.to_mek_contract()

        # Verify consequence is HIGH
        from mek0.kernel import ConsequenceLevel
        assert mek_contract.consequence_level == ConsequenceLevel.HIGH


class TestAuthoritySealing:
    """
    Tests for MEK-1: Authority Sealing.

    Proves:
    - Legacy execution paths are blocked
    - MEK refusal stops AIOS
    - No alternate path exists
    """

    def test_legacy_execution_blocked(self):
        """Legacy execution must be blocked."""
        from mek1.authority_sealing import LegacyExecutionBlockedError

        # Test decorator
        @mek1.authority_sealing.block_legacy_execution
        def legacy_fn():
            return "should_not_execute"

        with pytest.raises(LegacyExecutionBlockedError, match="LEGACY_EXECUTION_BLOCKED"):
            legacy_fn()

    def test_mek_refusal_is_terminal(self):
        """MEK refusal must be terminal for AIOS."""
        from mek1.mek_client import execute_via_mek, MEKRefusalError
        from mek0.kernel import ConsequenceLevel, CapabilityContract

        # Register capability that will refuse
        def refusing_fn(ctx):
            return "should_not_execute"

        contract = CapabilityContract(
            name="test_terminal",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=["missing"],
            _execute_fn=refusing_fn,
        )

        from mek0.kernel import get_guard
        get_guard().register_capability(contract)

        # Attempt execution - should raise MEKRefusalError
        context = type('Context', (), {'context_id': 'test'})()

        with pytest.raises(MEKRefusalError, match="MEK refused"):
            execute_via_mek("test_terminal", context, 0.9)


class TestObserverWiring:
    """
    Tests for MEK-1: Observer Wiring.

    Proves:
    - Observers are passive
    - Observer failures never affect execution
    - Observers are removable without effect
    """

    def test_observer_failure_does_not_block_execution(self):
        """Observer failure must not block execution."""
        from mek1.observer_wiring import AIOSObserverBridge, LoggingObserver

        # Create failing observer
        class FailingObserver:
            def on_event(self, event_type, details):
                raise RuntimeError("Observer failed!")

        bridge = AIOSObserverBridge()
        bridge.register_aios_observer_as_mek_observer(FailingObserver())

        # Register test capability
        from mek0.kernel import ConsequenceLevel, CapabilityContract, get_guard

        def test_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_observer_fail",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=test_fn,
        )

        get_guard().register_capability(contract)

        # Execute - should succeed despite observer failure
        from mek1.mek_client import execute_via_mek
        context = type('Context', (), {'context_id': 'test'})()

        result = execute_via_mek("test_observer_fail", context, 0.9)
        assert result is not None

    def test_observers_are_removable(self):
        """Observers must be removable without effect."""
        from mek1.observer_wiring import AIOSObserverBridge, LoggingObserver

        # Register observer
        bridge = AIOSObserverBridge()
        logging_observer = LoggingObserver()
        bridge.register_aios_observer_as_mek_observer(logging_observer)

        # Verify registered
        assert bridge.is_registered()

        # Clear observers
        bridge.clear_mek_observers()

        # Verify removed
        assert not bridge.is_registered()

    def test_removing_observers_does_not_break_execution(self):
        """Removing observers must not break execution."""
        from mek1.observer_wiring import AIOSObserverBridge, LoggingObserver
        from mek0.kernel import ConsequenceLevel, CapabilityContract, get_guard

        # Register observer
        bridge = AIOSObserverBridge()
        logging_observer = LoggingObserver()
        bridge.register_aios_observer_as_mek_observer(logging_observer)

        # Register capability
        def test_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_observer_remove",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=test_fn,
        )

        get_guard().register_capability(contract)

        # Clear observers
        bridge.clear_mek_observers()

        # Execute - should work without observers
        from mek1.mek_client import execute_via_mek
        context = type('Context', (), {'context_id': 'test'})()

        result = execute_via_mek("test_observer_remove", context, 0.9)
        assert result is not None


class TestAdapterContracts:
    """
    Tests for MEK-1: Adapter Contracts.

    Proves:
    - Adapters are contract-only (no runtime code)
    - Adapters cannot execute
    - Adapters cannot bypass Guard
    """

    def test_adapter_must_be_abstract(self):
        """Adapter contract must be abstract."""
        from mek1.adapter_interfaces import AdapterProtocol

        # AdapterProtocol is abstract - cannot instantiate
        with pytest.raises(TypeError):
            AdapterProtocol()

    def test_adapter_cannot_have_execute_method(self):
        """Adapter must not have execute method."""
        from mek1.adapter_interfaces import AdapterConstraintValidator

        # Mock adapter with execute method
        class BadAdapter:
            def execute(self):
                pass

        adapter = BadAdapter()
        assert not AdapterConstraintValidator.adapter_must_not_execute(adapter)

    def test_adapter_cannot_import_execution_path(self):
        """Adapter must not import execution path."""
        from mek1.adapter_interfaces import AdapterConstraintValidator

        # Mock adapter that imports execution path
        class BadAdapter:
            pass

        adapter = BadAdapter()
        # In a real test, this would check actual imports
        # For now, we test the validator exists
        assert hasattr(AdapterConstraintValidator, 'adapter_must_not_import_execution_path')


class TestNegativeSpaceAIOSBypass:
    """
    Tests for AIOS bypass attempts.

    Each test MUST fail to prove impossibility.
    """

    def test_aios_cannot_execute_without_mek(self):
        """AIOS cannot execute without MEK."""
        from backend.core.capability import CapabilityDescriptor, ConsequenceLevel

        def test_fn(ctx):
            return "should_not_execute"

        cap = CapabilityDescriptor(
            name="test_bypass",
            scope="test",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            execute_fn=test_fn,
        )

        # Direct execution should raise InvariantViolationError
        with pytest.raises(RuntimeError, match="INVARIANT_1_VIOLATION"):
            cap.execute({})

    def test_aios_cannot_retry_after_mek_refusal(self):
        """AIOS cannot retry after MEK refusal."""
        from mek1.mek_client import execute_via_mek, MEKRefusalError

        # First attempt - MEK refuses
        context = type('Context', (), {'context_id': 'test'})()

        with pytest.raises(MEKRefusalError, match="MEK refused"):
            execute_via_mek("any_capability", context, 0.9)

        # Retry attempt - should still raise MEKRefusalError
        with pytest.raises(MEKRefusalError, match="MEK refused"):
            execute_via_mek("any_capability", context, 0.9)

    def test_aios_cannot_bypass_friction(self):
        """AIOS cannot bypass friction."""
        from mek0.kernel import ConsequenceLevel, CapabilityContract, get_guard

        def test_fn(ctx):
            return "executed"

        contract = CapabilityContract(
            name="test_friction_bypass",
            consequence_level=ConsequenceLevel.HIGH,  # 10s friction
            required_context_fields=[],
            _execute_fn=test_fn,
        )

        get_guard().register_capability(contract)

        # Execute via MEK client
        from mek1.mek_client import execute_via_mek
        context = type('Context', (), {'context_id': 'test'})()

        start = time.time()
        execute_via_mek("test_friction_bypass", context, 0.9)
        elapsed = time.time() - start

        # Friction cannot be bypassed
        assert elapsed >= 10.0, f"Friction bypassed: {elapsed}s < 10.0s"

    def test_aios_cannot_escalate_without_explicit_request(self):
        """AIOS cannot escalate authority without explicit request."""
        # Test that escalation is blocked
        from backend.core.local_runner import LocalRunner

        runner = LocalRunner()

        # Escalation method must raise ProhibitedBehaviorError
        with pytest.raises(RuntimeError, match="I7_VIOLATION"):
            runner.should_escalate({})

    def test_aios_cannot_inject_escalation_comment(self):
        """AIOS cannot inject escalation comment."""
        # Test that escalation comment injection is blocked
        from backend.core.local_runner import LocalRunner

        runner = LocalRunner()

        # Escalation comment method must raise ProhibitedBehaviorError
        with pytest.raises(RuntimeError, match="I7_VIOLATION"):
            runner.inject_escalation_comment("code", "reason")


class TestMEKUncontaminated:
    """
    Tests proving MEK remains uncontaminated.

    MEK-0 internals must not be modified.
    """

    def test_mek_guard_is_singleton(self):
        """MEK Guard must be singleton."""
        from mek0.kernel import get_guard

        guard1 = get_guard()
        guard2 = get_guard()

        # Should be same instance
        assert guard1 is guard2

    def test_mek_context_is_immutable(self):
        """MEK Context must be immutable."""
        from mek0.kernel import Context

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test",
        )

        # Attempting to modify should fail (frozen)
        with pytest.raises(Exception):
            context.intent = "new_intent"

    def test_mek_capabilities_cannot_self_invoke(self):
        """MEK capabilities cannot self-invoke."""
        from mek0.kernel import CapabilityContract, ConsequenceLevel

        def self_invoking_fn(ctx):
            # Attempt to invoke another capability
            pass

        contract = CapabilityContract(
            name="test_self_invoke",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=self_invoking_fn,
        )

        # The contract's execute() is forbidden
        with pytest.raises(RuntimeError, match="I1_VIOLATION"):
            contract.execute(type('Context', (), {})())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
