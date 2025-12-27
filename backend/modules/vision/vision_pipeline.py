from __future__ import annotations

"""
vision_pipeline.py
UPDATED: Integrated Job Queue to prevent VRAM collision.
"""

import base64
import time
import threading
from typing import Any, Dict, Optional

import requests

from backend.core.config import (
    OLLAMA_URL,
    VISION_MODEL_NAME,
    VISION_ENABLED,
    OLLAMA_REQUEST_TIMEOUT_SECONDS,
    MAX_CONCURRENT_HEAVY_REQUESTS,
)
from backend.modules.telemetry.history import history_logger
from backend.modules.common.timeout_policy import run_with_retries

# 🟢 NEW: Import Queue Manager
from backend.modules.jobs.queue_manager import (
    enqueue_job,
    try_acquire_next_job,
    get_job,
    mark_job_done,
    mark_job_failed,
)

# =========================
# Size guards
# =========================

MAX_VISION_PROMPT_CHARS = 4000
MAX_VISION_OUTPUT_CHARS = 8000
MAX_ERROR_CHARS = 600


def _truncate_with_notice(text: Any, limit: int, label: str) -> str:
    if text is None: return ""
    if not isinstance(text, str): text = str(text)
    if len(text) <= limit: return text
    head = text[: max(0, limit - 200)]
    return head + f" [Truncated {label}: original length {len(text)} > {limit}]"

def _clamp_prompt(text: Any) -> str:
    return _truncate_with_notice(text, MAX_VISION_PROMPT_CHARS, "prompt")

def _clamp_output_text(text: Any) -> str:
    if text is None: return ""
    if not isinstance(text, str): text = str(text)
    if len(text) <= MAX_VISION_OUTPUT_CHARS: return text
    return text[: max(0, MAX_VISION_OUTPUT_CHARS - 200)] + "\n\n[Output truncated]"

# =========================
# Concurrency + timing
# =========================

_VISION_SEMAPHORE = threading.BoundedSemaphore(value=MAX_CONCURRENT_HEAVY_REQUESTS)

def _log_timing(model_name: str, duration_s: float, status: str, error: Optional[str] = None) -> None:
    try:
        if history_logger:
            history_logger.log({
                "kind": "pipeline_timing",
                "stage": "vision",
                "model": model_name,
                "duration_s": round(float(duration_s), 3),
                "status": status,
                "error": error,
            })
    except Exception:
        pass

def _call_ollama_vision(*, image_b64: str, user_prompt: str, model_name: str, mode: str) -> str:
    base_prompt = user_prompt or ""
    mode = (mode or "auto").strip().lower()

    if mode == "describe": prefix = "You are a visual assistant. Briefly describe this image for a developer:\n\n"
    elif mode == "ocr": prefix = "Extract all readable text from this image. Return raw text only:\n\n"
    elif mode == "code": prefix = "You are helping with code/UI from a screenshot. Explain only the relevant technical details:\n\n"
    elif mode == "debug": prefix = "The user is debugging an issue. Carefully describe visible errors and clues from this image:\n\n"
    else: prefix = ""

    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": model_name,
        "prompt": prefix + base_prompt,
        "stream": False,
        "images": [image_b64],
    }

    resp = requests.post(url, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json().get("response", "") or ""

def _run_with_timeout(fn, model_name: str):
    return run_with_retries(
        fn=fn,
        label="vision",
        max_retries=1,
        base_delay_s=1.0,
        timeout_s=OLLAMA_REQUEST_TIMEOUT_SECONDS,
        timing_cb=None,
        is_retryable_error=None,
    )

# =========================
# Public entrypoint
# =========================

def run_vision(
    image_bytes: bytes,
    user_prompt: str = "",
    mode: str = "auto",
    model_name: Optional[str] = None,
    profile_id: Optional[str] = None # 🟢 Added profile_id support
) -> str:
    """
    Main vision entrypoint.
    MANAGED by Queue: Ensures proper VRAM scheduling.
    """
    if not VISION_ENABLED:
        return "Vision is disabled in config."

    effective_model = model_name or VISION_MODEL_NAME
    if not image_bytes: return "(No image data received.)"
    safe_prompt = _clamp_prompt(user_prompt)

    # 1. Enqueue Job
    job_profile = profile_id or "default"
    job = enqueue_job(profile_id=job_profile, kind="vision", meta={"mode": mode})

    # 2. Wait for execution slot (with timeout)
    acquired = try_acquire_next_job(job_profile)
    if not acquired or acquired.id != job.id:
        start_wait = time.time()
        max_wait = 300.0  # 5 minutes timeout
        while time.time() - start_wait < max_wait:
            acquired = try_acquire_next_job(job_profile)
            if acquired and acquired.id == job.id:
                break
            snapshot = get_job(job.id)
            if snapshot is None or snapshot.state in ("failed", "cancelled"):
                return "Vision job cancelled or failed in queue."
            time.sleep(0.1)
        else:
            # Timeout reached
            return "Vision job timed out waiting in queue."

    try:
        # Base64 Encode
        image_b64 = base64.b64encode(image_bytes).decode("ascii")

        # Execution
        start = time.monotonic()
        status, error_msg = "ok", None

        # 3. Global Semaphore (VRAM Protection)
        _VISION_SEMAPHORE.acquire()
        try:
            def _call():
                return _call_ollama_vision(
                    image_b64=image_b64,
                    user_prompt=safe_prompt,
                    model_name=effective_model,
                    mode=mode or "auto",
                )
            result = _run_with_timeout(_call, effective_model)

            # Phase B: Add confidence validation
            try:
                from backend.modules.perception.vision_confidence import validate_vision_result
                vision_result = {"response": result, "mode": mode}
                validated_result = validate_vision_result(vision_result, mode)
                confidence_meta = validated_result.get("confidence_metadata", {})
                # Log confidence for observability
                if history_logger:
                    history_logger.log({
                        "mode": "vision_confidence",
                        "confidence_score": confidence_meta.get("confidence_score"),
                        "confidence_level": confidence_meta.get("confidence_level"),
                        "requires_confirmation": confidence_meta.get("requires_confirmation"),
                    })
            except Exception as e:
                # Use print since logger not available
                print(f"[VISION] Confidence validation failed: {e}")

            final_text = _clamp_output_text(result)
        except Exception as e:
            status = "error"
            error_msg = _truncate_with_notice(str(e), MAX_ERROR_CHARS, "Error")
            final_text = f"Vision stage failed: {error_msg}"
        finally:
            duration = time.monotonic() - start
            _log_timing(effective_model, duration, status, error_msg)
            _VISION_SEMAPHORE.release()

        mark_job_done(job.id)
        return final_text

    except Exception as e:
        mark_job_failed(job.id, str(e))
        return f"Vision Error: {e}"