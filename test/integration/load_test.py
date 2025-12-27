#!/usr/bin/env python3
"""
load_test.py

Light load test for AIOS components.
"""

import sys
import os
import time
import threading

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

def load_jobs():
    """Load test jobs."""
    from backend.modules.jobs.queue_manager import enqueue_job, try_acquire_next_job, mark_job_done

    for i in range(10):
        job = enqueue_job(profile_id='load_test', kind='vision', meta={'load': i})
        print(f"Enqueued {job.id}")

    for i in range(10):
        acquired = try_acquire_next_job('load_test')
        if acquired:
            mark_job_done(acquired.id)
            print(f"Processed {acquired.id}")
        else:
            print("No job to acquire")
        time.sleep(0.1)

def load_confirmations():
    """Load test confirmations."""
    from backend.modules.router.confirmation_router import create_confirmation_request

    for i in range(5):
        conf = create_confirmation_request(f'Load test {i}', {'test': i}, {'level': 'low'}, ttl_seconds=10)
        print(f"Created confirmation {conf['token']}")

    time.sleep(12)  # Wait for expiry

def load_permissions():
    """Load test permissions."""
    from backend.modules.security.permission_manager import grant_permission, consume_permission

    for i in range(5):
        perm = grant_permission(profile_id='load_perm', scope=f'load:op{i}', max_uses=3, reason='load test')
        for j in range(3):
            consumed = consume_permission(profile_id='load_perm', scope=f'load:op{i}', auth_level_min=3)
            if not consumed:
                break
        print(f"Processed permission {perm['id']}")

def main():
    print("Starting load tests...")

    threads = []
    threads.append(threading.Thread(target=load_jobs))
    threads.append(threading.Thread(target=load_confirmations))
    threads.append(threading.Thread(target=load_permissions))

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    print("Load tests complete.")

if __name__ == "__main__":
    main()