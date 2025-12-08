from __future__ import annotations

"""
timeout_policy.py

Shared timeout + retry helper for Ollama-bound stages.

Goal (V3.4.x):

Provide a small, reusable primitive that wraps a callable with:

- hard per-call timeout
- bounded retries with backoff
- optional timing callback for observability

This module is deliberately generic:

- It does NOT know about models, stages, or history.
- Callers provide:
    - a zero-arg function fn() that performs the actual work
    - a label string (e.g. "coder", "chat_planner", "vision")
    - retry and timeout parameters (usually from config)
    - an optional timing_cb(label, duration_s, status, error) function

Status values passed to timing_cb:

- "ok"      -> fn completed successfully
- "timeout" -> call hit the timeout
- "error"   -> fn raised an exception
- "give_up" -> final failure after exhausting retries (same error value)

IMPORTANT:

- This helper is best-effort. It should not raise anything OTHER than the
  original fn exception (on final failure).
"""

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


def _default_is_retryable_error(exc: BaseException) -> bool:
    """
    Very small heuristic for retryable errors.

    Callers can provide their own predicate if they want to be stricter/looser.
    """
    # Timeouts are usually retryable.
    if isinstance(exc, FuturesTimeoutError):
        return True

    # Network-ish issues are often transient.
    # We don't import requests here to avoid coupling; callers that care
    # can pass their own predicate instead.
    text = repr(exc).lower()
    transient_markers = [
        "timeout",
        "temporarily unavailable",
        "connection aborted",
        "connection reset",
        "connection refused",
        "broken pipe",
        "network is unreachable",
        "tlsv1",
        "ssl",
    ]
    return any(m in text for m in transient_markers)


def run_with_retries(
    fn: Callable[[], T],
    label: str,
    max_retries: int,
    base_delay_s: float,
    timeout_s: float,
    timing_cb: Optional[Callable[[str, float, str, Optional[str]], None]] = None,
    is_retryable_error: Optional[Callable[[BaseException], bool]] = None,
) -> T:
    """
    Run fn with timeout + retry semantics.

    Parameters:
        fn:
            Zero-argument callable performing the work (e.g. Ollama call).

        label:
            Short identifier used only for timing_cb (e.g. "coder", "chat_planner").

        max_retries:
            Number of times to retry AFTER the initial attempt.
            Total attempts = max_retries + 1.
            Use 0 to disable retries (still enforces timeout).

        base_delay_s:
            Initial sleep between retries (e.g. 0.5 or 1.0).
            Each retry uses simple exponential backoff: delay *= 2.

        timeout_s:
            Per-attempt timeout in seconds.
            If <= 0, the call is treated as "no timeout" (not recommended).

        timing_cb:
            Optional callback(label, duration_s, status, error_text).
            Called once per attempt, including final failure attempts.
            Must NOT raise; this function ignores any exceptions from it.

        is_retryable_error:
            Optional predicate(exc) -> bool deciding if we should retry.
            If None, uses _default_is_retryable_error.

    Returns:
        The value returned by fn() if any attempt succeeds.

    Raises:
        The last exception from fn() (or timeout) if all attempts fail.
    """
    if max_retries < 0:
        max_retries = 0
    if base_delay_s < 0:
        base_delay_s = 0.0

    retry_pred = is_retryable_error or _default_is_retryable_error
    delay = float(base_delay_s)

    last_exc: Optional[BaseException] = None

    # We use a tiny executor per call to mirror existing *_run_with_timeout
    # helpers without forcing callers to change their code structure.
    for attempt in range(max_retries + 1):
        start = time.monotonic()
        status = "ok"
        error_text: Optional[str] = None

        try:
            if timeout_s and timeout_s > 0:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(fn)
                    result = future.result(timeout=timeout_s)
            else:
                # No timeout requested: run fn directly.
                result = fn()

            duration = time.monotonic() - start

            if timing_cb:
                try:
                    timing_cb(label, duration, status, None)
                except Exception:
                    # Timing must be best-effort only.
                    pass

            return result

        except FuturesTimeoutError as exc:
            last_exc = exc
            status = "timeout"
            error_text = str(exc) or "timeout"
        except BaseException as exc:
            last_exc = exc
            status = "error"
            error_text = str(exc) or exc.__class__.__name__

        # Attempt failed; record timing for this attempt.
        duration = time.monotonic() - start
        if timing_cb:
            try:
                timing_cb(label, duration, status, error_text)
            except Exception:
                # Again, timing must not interfere with main flow.
                pass

        # Decide whether to retry.
        if attempt < max_retries and last_exc and retry_pred(last_exc):
            if delay > 0:
                time.sleep(delay)
                delay *= 2.0
            continue

        # No more retries, or non-retryable error.
        # Final "give_up" timing for observability (optional).
        if timing_cb:
            try:
                timing_cb(label, 0.0, "give_up", error_text)
            except Exception:
                pass

        # Propagate the last exception as-is.
        if isinstance(last_exc, BaseException):
            raise last_exc

        # Defensive: in theory we should always have last_exc here.
        raise RuntimeError(f"{label}: run_with_retries failed with unknown error state")
