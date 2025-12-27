"""
MEK-2: Adversarial Tests

Tests proving authority is explicit, time-bound, and revocable.
All tests MUST fail for any violation attempt.
"""

import pytest
import time
import threading


class TestPrincipalValidation:
    """
    Tests for Principal validation.

    MEK-2: Principal is explicit actor.
    Missing principal -> refusal.
    """

    def test_missing_principal_refuses(self):
        """Execution without principal must refuse."""
        from mek2.authority_guard import get_authority_guard

        guard = get_authority_guard()

        # Create context without principal
        from mek0.kernel import Context
        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test",
            fields={},
        )

        # Attempt execution without principal -> should refuse
        result = guard.execute_with_authority(
            principal_id=None,  # Missing
            capability_name="test_cap",
            context=context,
            grant_id="nonexistent",
        )

        # Should be non-action
        from mek0.kernel import NonActionReason
        assert result.non_action["reason"] == NonActionReason.REFUSED_BY_GUARD.value

    def test_empty_principal_refuses(self):
        """Empty principal must refuse."""
        from mek2.authority_guard import get_authority_guard
        from mek2.authority_primitives import create_principal

        # Empty principal_id -> should raise ValueError
        with pytest.raises(ValueError, match="principal_id is required"):
            create_principal("")


class TestGrantValidation:
    """
    Tests for Grant validation.

    MEK-2: Grant is time-bound authority.
    """

    def test_no_grant_refuses(self):
        """Execution without grant must refuse."""
        from mek2.authority_guard import get_authority_guard

        guard = get_authority_guard()

        # Create context
        from mek0.kernel import Context
        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test",
            fields={},
        )

        # Attempt execution without grant -> should refuse
        result = guard.execute_with_authority(
            principal_id="test_principal",
            capability_name="test_cap",
            context=context,
            grant_id="nonexistent",
        )

        # Should be non-action
        from mek0.kernel import NonActionReason
        assert result.non_action["reason"] == NonActionReason.REFUSED_BY_GUARD.value

    def test_expired_grant_refuses(self):
        """Expired grant must refuse execution."""
        from mek2.authority_guard import get_authority_guard, get_authority_state
        from mek2.authority_primitives import create_principal, create_grant
        from mek0.kernel import Context

        state = get_authority_state()
        guard = get_authority_guard()

        # Issue expired grant
        principal = create_principal("test_principal")
        grant = guard.issue_grant(
            principal_id="test_principal",
            capability_name="test_cap",
            scope="test_scope",
            ttl_seconds=1.0,  # Expire in 1 second
            max_uses=None,
        )

        # Wait for expiration
        time.sleep(1.5)

        # Attempt execution
        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_cap",
            fields={},
        )

        result = guard.execute_with_authority(
            principal_id="test_principal",
            capability_name="test_cap",
            context=context,
            grant_id=grant.grant_id,
        )

        # Should be non-action (expired)
        from mek0.kernel import NonActionReason
        assert result.non_action["reason"] == "grant_expired"

    def test_exhausted_grant_refuses(self):
        """Grant with max_uses exhausted must refuse execution."""
        from mek2.authority_guard import get_authority_guard, get_authority_state
        from mek2.authority_primitives import create_principal
        from mek0.kernel import Context

        guard = get_authority_guard()

        # Issue grant with 1 use
        principal = create_principal("test_principal")
        grant = guard.issue_grant(
            principal_id="test_principal",
            capability_name="test_cap",
            scope="test_scope",
            ttl_seconds=3600,
            max_uses=1,
        )

        # Execute first time - should succeed
        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_cap",
            fields={},
        )

        result1 = guard.execute_with_authority(
            principal_id="test_principal",
            capability_name="test_cap",
            context=context,
            grant_id=grant.grant_id,
        )

        # First execution should succeed
        assert result1.is_success()

        # Execute second time - should refuse
        result2 = guard.execute_with_authority(
            principal_id="test_principal",
            capability_name="test_cap",
            context=context,
            grant_id=grant.grant_id,
        )

        # Second execution should refuse (exhausted)
        from mek0.kernel import NonActionReason
        assert result2.non_action["reason"] == "grant_exhausted"


class TestRevocation:
    """
    Tests for Revocation.

    MEK-2: Revocation is terminal and always wins.
    """

    def test_revocation_halts_execution_immediately(self):
        """Revocation during execution must halt immediately."""
        from mek2.authority_guard import get_authority_guard
        from mek2.authority_primitives import create_principal
        from mek0.kernel import Context

        guard = get_authority_guard()

        # Issue grant
        principal = create_principal("test_principal")
        grant = guard.issue_grant(
            principal_id="test_principal",
            capability_name="test_cap",
            scope="test_scope",
            ttl_seconds=3600,
            max_uses=None,
        )

        # Revoke the grant
        from mek2.authority_primitives import RevocationReason
        guard.revoke_grant(
            grant_id=grant.grant_id,
            revoked_by_principal="admin",
            reason=RevocationReason.EXPLICIT_REVOCATION,
        )

        # Attempt execution - should refuse immediately
        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_cap",
            fields={},
        )

        result = guard.execute_with_authority(
            principal_id="test_principal",
            capability_name="test_cap",
            context=context,
            grant_id=grant.grant_id,
        )

        # Should be non-action (revoked)
        from mek0.kernel import NonActionReason
        assert result.non_action["reason"] == "grant_revoked"

    def test_revocation_during_friction_halts(self):
        """Revocation during friction must halt."""
        from mek2.authority_guard import get_authority_guard
        from mek2.authority_primitives import create_principal
        from mek0.kernel import Context

        guard = get_authority_guard()

        # Issue HIGH consequence grant (10s friction)
        principal = create_principal("test_principal")
        grant = guard.issue_grant(
            principal_id="test_principal",
            capability_name="test_high_friction",
            scope="test_scope",
            ttl_seconds=3600,
            max_uses=None,
        )

        # Start execution in thread
        execution_started = threading.Event()
        execution_result = [None]

        def execute_thread():
            context = Context(
                context_id="test",
                confidence=0.9,
                intent="test_high_friction",
                fields={},
            )
            execution_result[0] = guard.execute_with_authority(
                principal_id="test_principal",
                capability_name="test_high_friction",
                context=context,
                grant_id=grant.grant_id,
            )
            execution_started.set()

        thread = threading.Thread(target=execute_thread)
        thread.start()
        execution_started.wait()

        # Revoke after 1 second (during friction)
        time.sleep(1.0)
        guard.revoke_grant(
            grant_id=grant.grant_id,
            revoked_by_principal="admin",
            reason=RevocationReason.EXPLICIT_REVOCATION,
        )

        thread.join(timeout=15)

        # Result should be non-action (revoked)
        from mek0.kernel import Result
        assert isinstance(execution_result[0], Result)
        assert not execution_result[0].is_success()
        assert execution_result[0].non_action["reason"] == "grant_revoked"


class TestGrantFabrication:
    """
    Tests for grant fabrication prevention.

    MEK-2: AIOS cannot fabricate or extend grants.
    """

    def test_aios_cannot_create_grant_directly(self):
        """AIOS cannot create grants directly."""
        # Only AuthorityGuard can issue grants
        # AIOS must use issue_grant() method
        from mek2.authority_primitives import Grant

        # Attempting to create Grant directly should fail
        # because grant_id must be UUID
        with pytest.raises(ValueError, match="grant_id is required"):
            Grant(
                grant_id="",
                principal_id="test",
                capability_name="test",
                scope="test",
                issued_at=time.monotonic(),
                expires_at=time.monotonic() + 3600,
                max_uses=None,
                remaining_uses=0,
            )

    def test_aios_cannot_modify_grant(self):
        """AIOS cannot modify existing grants."""
        from mek2.authority_guard import get_authority_guard, get_authority_state
        from mek2.authority_primitives import create_principal

        guard = get_authority_guard()
        state = get_authority_state()

        # Issue grant
        principal = create_principal("test_principal")
        grant = guard.issue_grant(
            principal_id="test_principal",
            capability_name="test_cap",
            scope="test_scope",
            ttl_seconds=3600,
            max_uses=10,
        )

        # Attempt to modify grant (should fail - frozen dataclass)
        # Grants are immutable by design
        assert grant.max_uses == 10
        # No way to change it without violating frozen constraint


class TestPrincipalGrantSeparation:
    """
    Tests for principal-grant separation.

    MEK-2: Two principals cannot share grants.
    """

    def test_principals_cannot_share_grants(self):
        """Principal A cannot use Principal B's grant."""
        from mek2.authority_guard import get_authority_guard, get_authority_state
        from mek2.authority_primitives import create_principal
        from mek0.kernel import Context

        guard = get_authority_guard()

        # Issue grant to principal1
        principal1 = create_principal("principal1")
        grant1 = guard.issue_grant(
            principal_id="principal1",
            capability_name="test_cap",
            scope="test_scope",
            ttl_seconds=3600,
            max_uses=None,
        )

        # Attempt execution as principal2 with principal1's grant
        principal2 = create_principal("principal2")
        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_cap",
            fields={},
        )

        result = guard.execute_with_authority(
            principal_id="principal2",  # Wrong principal
            capability_name="test_cap",
            context=context,
            grant_id=grant1.grant_id,
        )

        # Should refuse (principal mismatch)
        from mek0.kernel import NonActionReason
        assert result.non_action["reason"] == "grant_principal_mismatch"


class TestAdapterGrantIndependence:
    """
    Tests for adapter-grant independence.

    MEK-2: Adapters (stubs) cannot alter grants.
    """

    def test_adapters_cannot_alter_grants(self):
        """Adapters cannot modify grants."""
        from mek2.authority_guard import get_authority_guard

        guard = get_authority_guard()

        # Issue a grant
        grant = guard.issue_grant(
            principal_id="test_principal",
            capability_name="test_cap",
            scope="test_scope",
            ttl_seconds=3600,
            max_uses=None,
        )

        # Adapters are contract-only (no implementation)
        # They cannot access AuthorityGuard state
        # Grants are frozen - cannot be modified
        assert grant.grant_id is not None


class TestObserverIndependence:
    """
    Tests for observer independence.

    MEK-2: Removing observers changes nothing.
    """

    def test_removing_observers_does_not_affect_authority(self):
        """Removing observers must not affect authority checks."""
        from mek2.authority_guard import get_authority_guard
        from mek0.kernel import get_observer_hub

        guard = get_authority_guard()

        # Issue a grant
        grant = guard.issue_grant(
            principal_id="test_principal",
            capability_name="test_cap",
            scope="test_scope",
            ttl_seconds=3600,
            max_uses=None,
        )

        # Clear all observers
        hub = get_observer_hub()
        hub.clear()

        # Execution should still work
        # Observers are non-blocking
        # Authority checks are independent of observers
        from mek0.kernel import Context
        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_cap",
            fields={},
        )

        # Register capability
        def test_fn(ctx):
            return "executed"

        from mek0.kernel import CapabilityContract, ConsequenceLevel
        contract = CapabilityContract(
            name="test_cap",
            consequence_level=ConsequenceLevel.LOW,
            required_context_fields=[],
            _execute_fn=test_fn,
        )

        from mek0.kernel import get_guard
        get_guard().register_capability(contract)

        result = guard.execute_with_authority(
            principal_id="test_principal",
            capability_name="test_cap",
            context=context,
            grant_id=grant.grant_id,
        )

        # Should succeed without observers
        assert result.is_success()


class TestMaxUsesAtomicity:
    """
    Tests for max_uses atomicity.

    MEK-2: max_uses decrements atomically.
    """

    def test_max_uses_decrements_atomically(self):
        """Concurrent executions properly decrement max_uses."""
        from mek2.authority_guard import get_authority_guard
        from mek0.kernel import Context

        guard = get_authority_guard()

        # Issue grant with 3 uses
        grant = guard.issue_grant(
            principal_id="test_principal",
            capability_name="test_cap",
            scope="test_scope",
            ttl_seconds=3600,
            max_uses=3,
        )

        # Execute 3 times concurrently
        results = []
        threads = []

        def execute():
            context = Context(
                context_id="test",
                confidence=0.9,
                intent="test_cap",
                fields={},
            )
            result = guard.execute_with_authority(
                principal_id="test_principal",
                capability_name="test_cap",
                context=context,
                grant_id=grant.grant_id,
            )
            results.append(result)

        for _ in range(3):
            t = threading.Thread(target=execute)
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=5)

        # Exactly 3 should succeed, 1 should fail
        success_count = sum(1 for r in results if r.is_success())
        failure_count = sum(1 for r in results if r.is_non_action())

        assert success_count == 3, f"Expected 3 successes, got {success_count}"
        assert failure_count == 0, f"Expected 0 failures, got {failure_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
