#!/usr/bin/env python3
"""
test_e2e.py

Lightweight E2E Integration Test Harness for AIOS.
Exercises key integration paths without external dependencies.

Run with: python test/integration/test_e2e.py
"""

import time
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

def test_job_lifecycle():
    """Test job enqueue → run → cleanup."""
    print("Testing job lifecycle...")
    from backend.modules.jobs.queue_manager import enqueue_job, try_acquire_next_job, mark_job_done, get_queue_snapshot

    # Enqueue
    job = enqueue_job(profile_id='e2e_test', kind='vision', meta={'test': 'e2e'})
    assert job is not None, "Job enqueue failed"
    print(f"Enqueued job {job.id}")

    # Acquire
    acquired = try_acquire_next_job('e2e_test')
    assert acquired and acquired.id == job.id, "Job acquire failed"
    print(f"Acquired job {acquired.id}")

    # Complete
    mark_job_done(acquired.id)
    print(f"Completed job {acquired.id}")

    # Check cleanup
    snap = get_queue_snapshot('e2e_test')
    assert snap['profiles']['e2e_test']['queue_length'] == 0, "Job not cleaned up"
    print("Job lifecycle complete")


def test_confirmation_flow():
    """Test confirmation create → submit → expire."""
    print("Testing confirmation flow...")
    from backend.modules.router.confirmation_router import create_confirmation_request, submit_confirmation, get_active_confirmations

    # Create
    conf = create_confirmation_request('E2E test', {'action': 'test'}, {'level': 'medium'}, ttl_seconds=5)
    token = conf['token']
    print(f"Created confirmation {token}")

    # Check active
    active = get_active_confirmations()
    tokens = [c['token'] for c in active]
    assert token in tokens, "Confirmation not active"
    print("Confirmation is active")

    # Submit
    from backend.modules.router.confirmation_router import ConfirmationSubmit
    result = submit_confirmation(ConfirmationSubmit(token=token, decision='confirm'))
    assert result['status'] == 'confirmed', "Confirmation submit failed"
    print("Confirmation submitted")

    # Check expired
    time.sleep(6)
    active_after = get_active_confirmations()
    tokens_after = [c['token'] for c in active_after]
    assert token not in tokens_after, "Confirmation not expired"
    print("Confirmation expired properly")


def test_permission_flow():
    """Test permission grant → list → consume (read-only)."""
    print("Testing permission flow...")
    from backend.modules.security.permission_manager import grant_permission, get_active_permissions, consume_permission

    # Grant
    perm = grant_permission(profile_id='e2e_perm', scope='e2e:read', max_uses=2, reason='e2e test')
    assert perm['id'], "Permission grant failed"
    print(f"Granted permission {perm['id']}")

    # List
    active = get_active_permissions(profile_id='e2e_perm')
    assert len(active) == 1, "Permission not listed"
    print("Permission listed as active")

    # Consume
    consumed = consume_permission(profile_id='e2e_perm', scope='e2e:read', auth_level_min=3)
    assert consumed, "Permission consume failed"
    print("Permission consumed")

    # Consume again
    consumed2 = consume_permission(profile_id='e2e_perm', scope='e2e:read', auth_level_min=3)
    assert consumed2, "Second consume failed"
    print("Permission consumed again")

    # Consume third time should fail
    consumed3 = consume_permission(profile_id='e2e_perm', scope='e2e:read', auth_level_min=3)
    assert consumed3 is None, "Third consume should fail"
    print("Permission max uses enforced")


def test_error_paths():
    """Test invalid inputs and error handling."""
    print("Testing error paths...")
    from backend.modules.tools.tools_runtime import execute_tool
    from backend.modules.jobs.queue_manager import enqueue_job
    from backend.modules.security.permission_manager import grant_permission

    # Invalid tool
    result = execute_tool('')
    assert result['ok'] is False, "Invalid tool should fail"
    print("Invalid tool rejected")

    # Invalid job enqueue
    try:
        enqueue_job(profile_id='', kind='test')
        assert False, "Should raise ValueError"
    except ValueError:
        print("Invalid job enqueue rejected")

    # Invalid permission grant
    try:
        grant_permission(profile_id='', scope='test')
        assert False, "Should raise ValueError"
    except ValueError:
        print("Invalid permission grant rejected")


def main():
    """Run all E2E tests."""
    print("Starting AIOS E2E Integration Tests")
    print("=" * 40)

    try:
        test_job_lifecycle()
        print()
        test_confirmation_flow()
        print()
        test_permission_flow()
        print()
        test_error_paths()
        print()
        print("All E2E tests passed!")

    except Exception as e:
        print(f"E2E test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()