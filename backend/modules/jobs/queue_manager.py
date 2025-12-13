"""
queue_manager.py (V4.0 - Global Resource Aware)

Centralized Job Queue & Resource Governor.

UPGRADES:
- Global "Heavy" Job Tracking: Prevents VRAM OOM by enforcing MAX_CONCURRENT_HEAVY_REQUESTS.
- Resource Awareness: Jobs can be flagged as `is_heavy` (Code/Vision) or light.
- State Integrity: Ensures active counts are decremented correctly on failure/cancel.

Usage:
    # Enqueue a heavy job (default)
    job = enqueue_job(pid, "code", is_heavy=True)

    # Poll for permission to run
    job = try_acquire_next_job(pid)
    if job:
        # RUN...
        mark_job_done(job.id)
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, asdict, field
from typing import Any, Deque, Dict, List, Optional

from backend.modules.telemetry.history import history_logger
from backend.core.config import MAX_CONCURRENT_HEAVY_REQUESTS

@dataclass
class Job:
    """
    Represents a single queued job.
    V4 Adds: `is_heavy` flag for VRAM management.
    """
    id: int
    profile_id: str
    kind: str
    state: str  # "queued", "running", "done", "failed", "cancelled"
    is_heavy: bool
    created_ts: float
    started_ts: Optional[float] = None
    finished_ts: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# =========================
# Internal State
# =========================

_LOCK = threading.Lock()

# Per-profile FIFO queues of job IDs
_PROFILE_QUEUES: Dict[str, Deque[int]] = {}

# Global mapping of job_id -> Job
_JOBS: Dict[int, Job] = {}

# Which job is currently running for each profile (if any)
_ACTIVE_BY_PROFILE: Dict[str, int] = {}

# Global Resource Counters
_ACTIVE_HEAVY_COUNT = 0

# Monotonic job ID generator
_NEXT_JOB_ID = 1


# =========================
# Internal Helpers
# =========================

def _next_id() -> int:
    global _NEXT_JOB_ID
    jid = _NEXT_JOB_ID
    _NEXT_JOB_ID += 1
    return jid

def _log_queue_event(job: Job, event: str, note: Optional[str] = None) -> None:
    """Log queue transitions to history."""
    try:
        history_logger.log({
            "kind": "queue_event",
            "event": event,
            "job_id": job.id,
            "profile_id": job.profile_id,
            "job_kind": job.kind,
            "is_heavy": job.is_heavy,
            "global_heavy_count": _ACTIVE_HEAVY_COUNT,
            "meta": dict(job.meta),
            "note": note or "",
        })
    except Exception:
        pass


# =========================
# Public API
# =========================

def enqueue_job(
    profile_id: str,
    kind: str,
    meta: Optional[Dict[str, Any]] = None,
    is_heavy: bool = True,  # Default to True for safety (Code/Vision are heavy)
) -> Job:
    """
    Enqueue a new job.
    
    Args:
        is_heavy (bool): If True, this job will wait for a global VRAM slot.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        raise ValueError("profile_id must be a non-empty string")

    kind = (kind or "unknown").strip()
    meta = meta or {}
    now = time.time()

    with _LOCK:
        job_id = _next_id()
        job = Job(
            id=job_id,
            profile_id=profile_id,
            kind=kind,
            state="queued",
            is_heavy=is_heavy,
            created_ts=now,
            meta=dict(meta),
        )

        _JOBS[job_id] = job

        q = _PROFILE_QUEUES.get(profile_id)
        if q is None:
            q = deque()
            _PROFILE_QUEUES[profile_id] = q
        q.append(job_id)

    _log_queue_event(job, "queued")
    return job


def try_acquire_next_job(profile_id: str) -> Optional[Job]:
    """
    Attempts to start the next job for this profile.
    
    Checks TWO constraints:
    1. Per-Profile: Is this profile already running a job? (FIFO)
    2. Global VRAM: If job is heavy, are we below MAX_CONCURRENT_HEAVY_REQUESTS?
    """
    global _ACTIVE_HEAVY_COUNT
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return None

    with _LOCK:
        # Constraint 1: Profile Serialism
        active_id = _ACTIVE_BY_PROFILE.get(profile_id)
        if active_id is not None and active_id in _JOBS:
            # This profile is already busy.
            return None

        q = _PROFILE_QUEUES.get(profile_id)
        if not q:
            return None

        # Peek at the next job (don't pop yet)
        next_job_id = q[0]
        job = _JOBS.get(next_job_id)
        if not job:
            q.popleft() # Clean up zombie
            return None

        # Constraint 2: Global Heavy Limit
        if job.is_heavy:
            if _ACTIVE_HEAVY_COUNT >= MAX_CONCURRENT_HEAVY_REQUESTS:
                # VRAM Full. Everyone waits.
                return None

        # All clear! Activate the job.
        q.popleft() # Remove from queue
        job.state = "running"
        job.started_ts = time.time()
        
        _ACTIVE_BY_PROFILE[profile_id] = job.id
        
        if job.is_heavy:
            _ACTIVE_HEAVY_COUNT += 1

    _log_queue_event(job, "started")
    return job


def mark_job_done(job_id: int, note: Optional[str] = None) -> Optional[Job]:
    """
    Mark job as done and release resources (Profile slot & VRAM slot).
    """
    global _ACTIVE_HEAVY_COUNT
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None

        # Only release resources if it was actually running
        if job.state == "running":
            active_id = _ACTIVE_BY_PROFILE.get(job.profile_id)
            if active_id == job_id:
                _ACTIVE_BY_PROFILE.pop(job.profile_id, None)
            
            if job.is_heavy:
                _ACTIVE_HEAVY_COUNT = max(0, _ACTIVE_HEAVY_COUNT - 1)

        job.state = "done"
        job.finished_ts = time.time()

    _log_queue_event(job, "done", note=note)
    return job


def mark_job_failed(job_id: int, error: str) -> Optional[Job]:
    """
    Mark job as failed and release resources.
    """
    global _ACTIVE_HEAVY_COUNT
    error = (error or "").strip()

    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None

        if job.state == "running":
            active_id = _ACTIVE_BY_PROFILE.get(job.profile_id)
            if active_id == job_id:
                _ACTIVE_BY_PROFILE.pop(job.profile_id, None)
            
            if job.is_heavy:
                _ACTIVE_HEAVY_COUNT = max(0, _ACTIVE_HEAVY_COUNT - 1)

        job.state = "failed"
        job.error = error
        job.finished_ts = time.time()

    _log_queue_event(job, "failed", note=error)
    return job


def cancel_job(job_id: int, note: Optional[str] = None) -> Optional[Job]:
    """
    Cancel a queued job. If running, use force_cancel (not impl here).
    """
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None

        # If it's already running, we can't just "cancel" it without killing the thread
        # (which Python makes hard). For now, we only allow cancelling queued jobs.
        if job.state != "queued":
            return job

        q = _PROFILE_QUEUES.get(job.profile_id)
        if q is not None:
            try:
                q.remove(job_id)
            except ValueError:
                pass

        job.state = "cancelled"
        job.finished_ts = time.time()

    _log_queue_event(job, "cancelled", note=note)
    return job


def get_job(job_id: int) -> Optional[Job]:
    """Read-only copy of a job."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        return Job(**asdict(job))


def get_queue_snapshot(profile_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get system state for Dashboard.
    Includes Global VRAM usage stats.
    """
    with _LOCK:
        if profile_id:
            profiles = [profile_id]
        else:
            profiles = sorted(set(_PROFILE_QUEUES.keys()) | set(_ACTIVE_BY_PROFILE.keys()))

        out: Dict[str, Any] = {
            "global_heavy_active": _ACTIVE_HEAVY_COUNT,
            "global_heavy_limit": MAX_CONCURRENT_HEAVY_REQUESTS,
            "profiles": {}
        }
        
        for pid in profiles:
            q_ids = list(_PROFILE_QUEUES.get(pid, []))
            active_id = _ACTIVE_BY_PROFILE.get(pid)

            active_job = _JOBS.get(active_id) if active_id is not None else None
            queued_jobs = [asdict(_JOBS[jid]) for jid in q_ids if jid in _JOBS]

            # Clean for JSON
            if active_job:
                active_job = asdict(active_job)

            out["profiles"][pid] = {
                "active_job": active_job,
                "queued_jobs": queued_jobs,
                "queue_length": len(queued_jobs)
            }

        return out