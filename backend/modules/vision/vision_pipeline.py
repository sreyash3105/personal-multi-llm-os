from __future__ import annotations

"""
vision_pipeline.py

Vision pipeline for the local AI assistant.

- Wraps a vision-capable Ollama model (e.g. llava:7b).
- Single entrypoint: run_vision(image_bytes, user_prompt, mode, model_name=None).

Separated from main code pipeline so code/study/chat don't depend on it.

V3.4.x — HARDENING:
- Uses OLLAMA_REQUEST_TIMEOUT_SECONDS for Ollama calls.
- Limits concurrent vision calls with a simple semaphore.
- Logs timing + status for each vision run via history_logger.
- Input/output size guards with transparent truncation notes.
- Stage-level timeout + retry wrapper via timeout_policy.run_with_retries.
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


# =========================
# Size guards
# =========================

MAX_VISION_PROMPT_CHARS = 4000
MAX_VISION_OUTPUT_CHARS = 8000
MAX_ERROR_CHARS = 600


def _truncate_with_notice(text: Any, limit: int, label: str) -> str:
    """
    Truncate text to a given limit and add a small notice if it was cut.

    Used both for prompts (safety) and for errors (so logs stay reasonable).
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    if len(text) <= limit:
        return text

    head = text[: max(0, limit - 200)]
    notice = f" [Truncated {label}: original length {len(text)} > {limit}]"
    return head + notice


def _clamp_prompt(text: Any) -> str:
    return _truncate_with_notice(text, MAX_VISION_PROMPT_CHARS, "prompt")


def _clamp_output_text(text: Any) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    if len(text) <= MAX_VISION_OUTPUT_CHARS:
        return text

    head = text[: max(0, MAX_VISION_OUTPUT_CHARS - 200)]
    notice = (
        "\n\n[Output truncated for safety — vision model attempted a very long answer. "
        "Some details may be missing.]"
    )
    return head + notice


# =========================
# Concurrency + timing
# =========================

_VISION_SEMAPHORE = threading.BoundedSemaphore(value=MAX_CONCURRENT_HEAVY_REQUESTS)


def _log_timing(model_name: str, duration_s: float, status: str, error: Optional[str] = None) -> None:
    """
    Record a small timing record for dashboard.

    kind: "pipeline_timing"
      - stage: "vision"
      - model: model name used
      - duration_s: float seconds
      - status: "ok" | "error" | "timeout"
      - error: optional error string
    """
    try:
        history_logger.log(
            {
                "kind": "pipeline_timing",
                "stage": "vision",
                "model": model_name,
                "duration_s": round(float(duration_s), 3),
                "status": status,
                "error": error,
            }
        )
    except Exception:
        # timing logs must not break main flow
        pass


def _call_ollama_vision(
    *,
    image_b64: str,
    user_prompt: str,
    model_name: str,
    mode: str,
) -> str:
    """
    Perform the actual HTTP POST to Ollama's /api/generate with image support.

    We send:
      {
        "model": model_name,
        "prompt": prompt_text,
        "images": [image_b64],
        "stream": false
      }

    The prompt_text incorporates the mode (auto/describe/ocr/code/debug/...).
    """
    # Build mode-prefixed prompt
    base_prompt = user_prompt or ""
    mode = (mode or "auto").strip().lower()

    if mode == "describe":
        prefix = "You are a visual assistant. Briefly describe this image for a developer:\n\n"
    elif mode == "ocr":
        prefix = "Extract all readable text from this image. Return raw text only:\n\n"
    elif mode == "code":
        prefix = "You are helping with code/UI from a screenshot. Explain only the relevant technical details:\n\n"
    elif mode == "debug":
        prefix = "The user is debugging an issue. Carefully describe visible errors and clues from this image:\n\n"
    else:
        prefix = ""

    prompt_text = prefix + base_prompt

    url = f"{OLLAMA_URL}/api/generate"
    payload: Dict[str, Any] = {
        "model": model_name,
        "prompt": prompt_text,
        "stream": False,
        "images": [image_b64],
    }

    resp = requests.post(
        url,
        json=payload,
        timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", "") or ""


def _run_with_timeout(fn, model_name: str):
    """
    Wrap a vision call with timeout + retry semantics via timeout_policy.

    - per-attempt timeout = OLLAMA_REQUEST_TIMEOUT_SECONDS
    - max_retries = 1 (initial + 1 retry)
    """
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
) -> str:
    """
    Main vision entrypoint for the rest of the system.

    Parameters:
      image_bytes:
        Raw bytes of the image (PNG/JPEG/etc).

      user_prompt:
        Optional text from the user. May be empty.

      mode:
        High-level hint:
          - "auto" (default)
          - "describe"
          - "ocr"
          - "code"
          - "debug"
        Others are treated as "auto".

      model_name:
        Override model name. Defaults to VISION_MODEL_NAME.

    Guardrails:
      - If VISION_ENABLED is False, returns an explanatory string immediately.
      - If no image data, returns a short message.
      - Input prompt is clamped in length.
      - Output text is clamped in length.
      - Concurrency limited by _VISION_SEMAPHORE.
      - HTTP timeout + retry via timeout_policy.
      - timing logged via history_logger (pipeline_timing stage="vision").
    """
    if not VISION_ENABLED:
        return "Vision is disabled in config (VISION_ENABLED = False)."

    effective_model = model_name or VISION_MODEL_NAME

    if not image_bytes:
        return "(No image data received.)"

    safe_prompt = _clamp_prompt(user_prompt)

    # Prepare image as base64 for Ollama
    try:
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
    except Exception as e:
        msg = _truncate_with_notice(f"Failed to base64-encode image: {e}", MAX_ERROR_CHARS, "Error")
        return f"Vision pipeline error: {msg}"

    start = time.monotonic()
    status = "ok"
    error_msg: Optional[str] = None

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
        return _clamp_output_text(result)
    except Exception as e:
        status = "error"
        error_msg = _truncate_with_notice(str(e), MAX_ERROR_CHARS, "Error")
        fallback = f"Vision stage failed: {error_msg}"
        return _clamp_output_text(fallback)
    finally:
        duration = time.monotonic() - start
        _log_timing(effective_model, duration, status, error_msg)
        _VISION_SEMAPHORE.release()
