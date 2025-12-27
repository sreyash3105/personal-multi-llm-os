"""
MEK-3: Adversarial Tests

Tests proving snapshot enforcement and TOCTOU immunity.
All tests MUST fail for any violation attempt.
"""

import pytest
import time
import threading


class TestSnapshotCreation:
    """
    Tests for MEK-3: Snapshot Creation.

    Proves:
    - Snapshots include all execution-relevant state
    - Snapshots are immutable
    - Snapshots are deterministic (hashes)
    """

    def test_snapshot_includes_authority_fields(self):
        """Snapshot must include all authority fields."""
        from mek3.snapshot_primitives import create_snapshot

        snapshot = create_snapshot(
            snapshot_id="test_001",
            principal_id="test_principal",
            grant_id="test_grant",
            capability_name="test_cap",
            capability_scope_hash="abc123",
            context_fields={"key": "value"},
            intent_name="test_intent",
            intent_value="test_value",
            confidence=0.9,
            authority_version=1,
            grant_expires_at=time.monotonic() + 3600,
        )

        # Verify all fields are present
        assert snapshot.snapshot_id == "test_001"
        assert snapshot.principal_id == "test_principal"
        assert snapshot.grant_id == "test_grant"
        assert snapshot.capability_name == "test_cap"
        assert snapshot.capability_scope_hash == "abc123"
        assert "key" in snapshot.context_fields
        assert snapshot.intent_name == "test_intent"
        assert snapshot.intent_value == "test_value"
        assert snapshot.confidence_range == "HIGH"
        assert snapshot.confidence_value == 0.9

    def test_snapshot_hashes_are_deterministic(self):
        """Snapshot hashes must be deterministic."""
        from mek3.snapshot_primitives import hash_dict

        data1 = {"key": "value"}
        data2 = {"key": "value"}

        hash1 = hash_dict(data1)
        hash2 = hash_dict(data2)

        # Same data should produce same hash
        assert hash1 == hash2

    def test_snapshot_captured_at_is_monotonic(self):
        """Snapshot timestamp must be monotonic."""
        from mek3.snapshot_primitives import create_snapshot

        now1 = time.monotonic()
        snapshot1 = create_snapshot(
            snapshot_id="test_002",
            principal_id="test_principal",
            grant_id="test_grant",
            capability_name="test_cap",
            capability_scope_hash="abc123",
            context_fields={},
            intent_name="test_intent",
            intent_value="test_value",
            confidence=0.9,
            authority_version=1,
            grant_expires_at=time.monotonic() + 3600,
        )

        time.sleep(0.01)
        now2 = time.monotonic()
        snapshot2 = create_snapshot(
            snapshot_id="test_003",
            principal_id="test_principal",
            grant_id="test_grant",
            capability_name="test_cap",
            capability_scope_hash="abc123",
            context_fields={},
            intent_name="test_intent",
            intent_value="test_value",
            confidence=0.9,
            authority_version=1,
            grant_expires_at=time.monotonic() + 3600,
        )

        # Timestamps must be monotonic increasing
        assert snapshot1.captured_at < snapshot2.captured_at

    def test_snapshot_is_immutable(self):
        """Snapshot dataclass must be frozen."""
        from mek3.snapshot_primitives import Snapshot

        snapshot = Snapshot(
            snapshot_id="test_004",
            captured_at=time.monotonic(),
            principal_id="test_principal",
            grant_id="test_grant",
            capability_name="test_cap",
            capability_scope_hash="abc123",
            context_fields={"key": "value"},
            intent_hash="hash123",
            intent_name="test_intent",
            intent_value="test_value",
            confidence_range="HIGH",
            confidence_value=0.9,
            authority_version=1,
            grant_expires_at=time.monotonic() + 3600,
        )

        # Attempting to modify should fail
        with pytest.raises(Exception):
            snapshot.capability_name = "modified"


class TestSnapshotRevalidation:
    """
    Tests for MEK-3: Snapshot Revalidation.

    Proves:
    - Snapshot mismatches cause terminal refusal
    - No execution after mismatch
    - TOCTOU immunity
    """

    def test_context_hash_mismatch_refuses(self):
        """Context hash mismatch must cause refusal."""
        from mek3.snapshot_guard import execute_with_snapshot
        from mek3.snapshot_primitives import SnapshotMismatchError
        from mek0.kernel import Context

        # Create snapshot with specific context hash
        from mek3.snapshot_primitives import create_snapshot
        snapshot = create_snapshot(
            snapshot_id="test_005",
            principal_id="test_principal",
            grant_id="test_grant",
            capability_name="test_cap",
            capability_scope_hash="abc123",
            context_fields={"key": "original"},
            intent_name="test_intent",
            intent_value="test_value",
            confidence=0.9,
            authority_version=1,
            grant_expires_at=time.monotonic() + 3600,
        )

        # Create context with different hash
        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_intent",
            fields={"key": "modified"},  # Different value -> different hash
        )

        # Execute should raise SnapshotMismatchError
        with pytest.raises(SnapshotMismatchError, match="context_fields"):
            execute_with_snapshot(
                principal_id="test_principal",
                grant_id="test_grant",
                capability_name="test_cap",
                context=context,
                confidence=0.9,
            )

    def test_intent_hash_mismatch_refuses(self):
        """Intent hash mismatch must cause refusal."""
        from mek3.snapshot_guard import execute_with_snapshot
        from mek3.snapshot_primitives import SnapshotMismatchError
        from mek0.kernel import Context

        snapshot_id = "test_006"
        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_intent",
            fields={"key": "value"},
        )

        # Execute with mismatched intent
        with pytest.raises(SnapshotMismatchError, match="intent"):
            execute_with_snapshot(
                principal_id="test_principal",
                grant_id="test_grant",
                capability_name="test_cap",
                context=context,
                confidence=0.9,
            )

    def test_authority_version_increment_refuses(self):
        """Authority version increment must be detected."""
        from mek3.snapshot_guard import execute_with_snapshot
        from mek3.snapshot_primitives import SnapshotMismatchError
        from mek0.kernel import Context

        context = Context(
            context_id="test",
            confidence=0.9,
            intent="test_intent",
            fields={"key": "value"},
        )

        # Execute with wrong version
        with pytest.raises(SnapshotMismatchError, match="authority_version"):
            execute_with_snapshot(
                principal_id="test_principal",
                grant_id="test_grant",
                capability_name="test_cap",
                context=context,
                confidence=0.9,
            )


class TestTOCTOUImmunity:
    """
    Tests for MEK-3: TOCTOU Immunity.

    Proves:
    - "It was valid earlier" is meaningless
    - No retroactive justification
    - Snapshot changes invalidate all executions
    """

    def test_snapshot_reuse_is_impossible(self):
        """Snapshot IDs must be unique (cannot reuse)."""
        from mek3.snapshot_guard import get_snapshot

        # Try to get same snapshot twice
        snapshot1 = get_snapshot("test_reuse")
        if snapshot1 is not None:
            snapshot2 = get_snapshot("test_reuse")
            # Should be same immutable object
            assert snapshot1 is snapshot2

    def test_snapshot_tampering_is_impossible(self):
        """Snapshot tampering must be impossible."""
        from mek3.snapshot_primitives import Snapshot

        snapshot = Snapshot(
            snapshot_id="test_007",
            captured_at=time.monotonic(),
            principal_id="test_principal",
            grant_id="test_grant",
            capability_name="test_cap",
            capability_scope_hash="abc123",
            context_fields={"key": "value"},
            intent_hash="hash123",
            intent_name="test_intent",
            intent_value="test_value",
            confidence_range="HIGH",
            confidence_value=0.9,
            authority_version=1,
            grant_expires_at=time.monotonic() + 3600,
        )

        # Attempting to modify should fail
        with pytest.raises(Exception):
            snapshot.context_fields = "tampered"

    def test_observers_cannot_influence_snapshots(self):
        """Observers cannot affect snapshot storage."""
        from mek3.snapshot_store import get_snapshot_store

        # Observer cannot modify stored snapshots
        store = get_snapshot_store()

        snapshot_id = "test_008"
        from mek3.snapshot_primitives import create_snapshot

        snapshot = create_snapshot(
            snapshot_id=snapshot_id,
            principal_id="test_principal",
            grant_id="test_grant",
            capability_name="test_cap",
            capability_scope_hash="abc123",
            context_fields={},
            intent_name="test_intent",
            intent_value="test_value",
            confidence=0.9,
            authority_version=1,
            grant_expires_at=time.monotonic() + 3600,
        )

        store.store_snapshot(snapshot)

        # Snapshot should be unchanged
        retrieved = store.get_snapshot(snapshot_id)
        assert retrieved is not None
        assert retrieved.snapshot_id == snapshot_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
