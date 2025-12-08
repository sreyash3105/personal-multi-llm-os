"""
queue_manager.py

Lightweight per-profile job queue for the Personal Local AI OS.

Goal (V3.4.x):
- Ensure only one "heavy" job per profile runs at a time.
- Additional jobs for the same profile are queued FIFO.
- Fully in-memory, no DB migrations.
- Best-effort logging into history (queue_event records).

This module is SAFE on its own:
- Importing it does NOT change any behavior.
- Nothing runs until other modules explicitly call its functions.

Planned integration points (later):
- chat_pipeline.py (smart chat)
- pipeline.py (coder / reviewer / judge / study)
- optionally vision_pipeline.py
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, asdict, field
from typing import Any, Deque, Dict, List, Optional

from history import history_logger


@dataclass
class Job:
    """
    Represents a single queued job.

    Fields:
      - id: unique integer within this process
      - profile_id: profile key (e.g. "A", "B", UUID, etc.)
      - kind: "code", "study", "chat_smart", "vision", etc.
      - state: "queued" | "running" | "done" | "failed" | "cancelled"
      - created_ts: UNIX timestamp when enqueued
      - started_ts / finished_ts: optional timestamps
      - meta: free-form dict for additional context (non-sensitive)
      - error: optional error message for failed jobs
    """
    id: int
    profile_id: str
    kind: str
    state: str
    created_ts: float
    started_ts: Optional[float] = None
    finished_ts: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# =========================
# Internal state
# =========================

_LOCK = threading.Lock()

# Per-profile FIFO queues of job IDs
_PROFILE_QUEUES: Dict[str, Deque[int]] = {}

# Global mapping of job_id -> Job
_JOBS: Dict[int, Job] = {}

# Which job is currently running for each profile (if any)
_ACTIVE_BY_PROFILE: Dict[str, int] = {}

# Monotonic job ID generator
_NEXT_JOB_ID = 1


# =========================
# Internal helpers
# =========================

def _next_id() -> int:
    """
    Generate a new unique job ID.
    Only safe to call under _LOCK.
    """
    global _NEXT_JOB_ID
    jid = _NEXT_JOB_ID
    _NEXT_JOB_ID += 1
    return jid


def _log_queue_event(job: Job, event: str, note: Optional[str] = None) -> None:
    """
    Best-effort history log for queue events.

    Record shape:

      {
        "kind": "queue_event",
        "event": "queued" | "started" | "done" | "failed" | "cancelled",
        "job_id": 12,
        "profile_id": "A",
        "job_kind": "code",
        "meta": {...},
        "note": "optional human-readable note",
      }

    Must never raise.
    """
    try:
        history_logger.log(
            {
                "kind": "queue_event",
                "event": event,
                "job_id": job.id,
                "profile_id": job.profile_id,
                "job_kind": job.kind,
                "meta": dict(job.meta) if isinstance(job.meta, dict) else {},
                "note": note or "",
            }
        )
    except Exception:
        # Queue logging must never break callers.
        pass


# =========================
# Public API
# =========================

def enqueue_job(
    profile_id: str,
    kind: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Job:
    """
    Enqueue a new job for a given profile.

    Returns the Job object in state="queued".

    Typical usage pattern (future):

        job = enqueue_job(profile_id, "chat_smart", {"chat_id": chat_id})
        acquired = try_acquire_next_job(profile_id)
        if acquired and acquired.id == job.id:
            # run the job now...
            ...
            mark_job_done(job.id)

    For now, this module is not wired; it is safe to just create jobs
    and later inspect get_queue_snapshot() from dashboard.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        raise ValueError("profile_id must be a non-empty string")

    kind = (kind or "unknown").strip() or "unknown"
    meta = meta or {}

    now = time.time()

    with _LOCK:
        job_id = _next_id()
        job = Job(
            id=job_id,
            profile_id=profile_id,
            kind=kind,
            state="queued",
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
    Try to start the next job for a profile.

    Behavior:
      - If there is already an active job for this profile, returns None.
      - Otherwise pops the next queued job (if any),
        marks it as running, sets started_ts, and returns it.

    This function does NOT execute the job; it only updates metadata.

    Intended usage:

        job = enqueue_job(profile_id, kind, meta)
        acquired = try_acquire_next_job(profile_id)
        if acquired and acquired.id == job.id:
            # This process can run the job.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return None

    with _LOCK:
        # Already running something for this profile?
        active_id = _ACTIVE_BY_PROFILE.get(profile_id)
        if active_id is not None and active_id in _JOBS:
            return None

        q = _PROFILE_QUEUES.get(profile_id)
        if not q:
            return None

        job_id = q.popleft()
        job = _JOBS.get(job_id)
        if not job:
            return None

        job.state = "running"
        job.started_ts = time.time()
        _ACTIVE_BY_PROFILE[profile_id] = job_id

    _log_queue_event(job, "started")
    return job


def mark_job_done(job_id: int, note: Optional[str] = None) -> Optional[Job]:
    """
    Mark a job as successfully completed.

    This will:
      - set state="done"
      - set finished_ts
      - clear active slot for that profile (allowing next job to start)

    Returns the updated Job object (or None if job_id not found).
    """
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None

        job.state = "done"
        job.finished_ts = time.time()

        active_id = _ACTIVE_BY_PROFILE.get(job.profile_id)
        if active_id == job_id:
            _ACTIVE_BY_PROFILE.pop(job.profile_id, None)

    _log_queue_event(job, "done", note=note)
    return job


def mark_job_failed(job_id: int, error: str) -> Optional[Job]:
    """
    Mark a job as failed.

    Similar to mark_job_done, but with state="failed" and an error message.
    """
    error = (error or "").strip()

    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None

        job.state = "failed"
        job.error = error
        job.finished_ts = time.time()

        active_id = _ACTIVE_BY_PROFILE.get(job.profile_id)
        if active_id == job_id:
            _ACTIVE_BY_PROFILE.pop(job.profile_id, None)

    _log_queue_event(job, "failed", note=error)
    return job


def cancel_job(job_id: int, note: Optional[str] = None) -> Optional[Job]:
    """
    Cancel a queued job (no-op if already started or finished).

    This does not interrupt running jobs; it only removes jobs still in the queue.
    """
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None

        if job.state != "queued":
            # Only queued jobs can be cancelled cleanly
            return job

        q = _PROFILE_QUEUES.get(job.profile_id)
        if q is not None:
            try:
                q.remove(job_id)
            except ValueError:
                # Already not in queue
                pass

        job.state = "cancelled"
        job.finished_ts = time.time()

    _log_queue_event(job, "cancelled", note=note)
    return job


def get_job(job_id: int) -> Optional[Job]:
    """
    Fetch a job by ID.

    Returns a shallow copy (new Job instance) so callers cannot mutate internals.
    """
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        return Job(**asdict(job))


def get_queue_snapshot(profile_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Return a JSON-serializable snapshot of the queues and active jobs.

    If profile_id is provided, only that profile's data is returned.
    Otherwise, all profiles are included.

    Shape:

      {
        "profiles": {
          "A": {
            "active_job": {...} | None,
            "queued_jobs": [...],
          },
          ...
        }
      }

    This is useful for future dashboard integration (/queue inspector).
    """
    with _LOCK:
        if profile_id:
            profiles = [profile_id]
        else:
            profiles = sorted(set(_PROFILE_QUEUES.keys()) | set(_ACTIVE_BY_PROFILE.keys()))

        out: Dict[str, Any] = {"profiles": {}}
        for pid in profiles:
            q_ids = list(_PROFILE_QUEUES.get(pid, []))
            active_id = _ACTIVE_BY_PROFILE.get(pid)

            active_job = _JOBS.get(active_id) if active_id is not None else None
            queued_jobs = [asdict(_JOBS[jid]) for jid in q_ids if jid in _JOBS]

            out["profiles"][pid] = {
                "active_job": asdict(active_job) if active_job else None,
                "queued_jobs": queued_jobs,
            }

        return out
