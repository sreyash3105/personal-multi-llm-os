"""
Vision pipeline for the local AI assistant.

- Wraps a vision-capable Ollama model (e.g. llava:7b)
- Single entrypoint: run_vision(image_bytes, user_prompt, mode)

Separated from main code pipeline so code/study/chat don't depend on it.

HARDNING BASE · Phase 2/3:
- Uses OLLAMA_REQUEST_TIMEOUT_SECONDS for Ollama calls.
- Limits concurrent vision calls with a simple semaphore.
- Logs timing + status for each vision run via history_logger.
- Input/output size guards with transparent truncation notes.
- Stage-level timeout wrapper + graceful fallback on errors.
"""

import base64
import threading
import time
from typing import Optional
import concurrent.futures

import requests

from config import (
    OLLAMA_URL,
    VISION_MODEL_NAME,
    VISION_ENABLED,
    OLLAMA_REQUEST_TIMEOUT_SECONDS,
    MAX_CONCURRENT_HEAVY_REQUESTS,
)
from history import history_logger


# =========================
# Size guards (input / output)
# =========================

# Vision prompts and outputs can be smaller than code, but we still guard them.
_MAX_INPUT_CHARS_VISION = 4000
_MAX_OUTPUT_CHARS_VISION = 8000


def _truncate_with_notice(text: str, limit: int, label: str) -> str:
    """
    Truncate text to `limit` characters and append a transparent note.

    label is a short identifier such as "Input" or "Output".
    """
    if not isinstance(text, str):
        text = str(text or "")
    if len(text) <= limit:
        return text
    head = text[:limit]
    return head + f"\n\n[{label} truncated for safety — original content was too long.]"


def _sanitize_input_text(text: str) -> str:
    """
    Guardrail for incoming user text before building the vision prompt.
    """
    return _truncate_with_notice(text or "", _MAX_INPUT_CHARS_VISION, "Input")


def _clamp_output_text(text: str) -> str:
    """
    Guardrail for model outputs before returning to caller.
    """
    return _truncate_with_notice(text or "", _MAX_OUTPUT_CHARS_VISION, "Output")


# =========================
# Concurrency guard
# =========================

# Vision is considered a "heavy" operation similar to /api/code.
# We use the same maximum as other heavy tasks, but this semaphore
# is local to vision. (Global concurrency is still bounded by CPU/GPU.)
_VISION_SEMAPHORE = threading.BoundedSemaphore(value=MAX_CONCURRENT_HEAVY_REQUESTS)


def _log_timing(stage: str, model_name: str, duration_s: float, status: str, error: str | None = None) -> None:
    """
    Best-effort timing logger into history.
    Failure here must never break the main flow.
    """
    try:
        history_logger.log(
            {
                "kind": "pipeline_timing",
                "stage": stage,
                "model": model_name,
                "duration_s": round(float(duration_s), 3),
                "status": status,
                "error": error,
            }
        )
    except Exception:
        # Logging is best-effort only.
        pass


def _run_with_timeout(fn, stage: str, model_name: str):
    """
    Stage-level timeout wrapper for vision.

    Even though call_ollama_vision already uses an HTTP timeout, this
    ensures the stage itself is bounded and cannot hang indefinitely
    if something goes wrong beneath requests.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        return future.result(timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS)


def call_ollama_vision(
    image_bytes: bytes,
    prompt: str,
    model_name: Optional[str] = None,
) -> str:
    """
    Low-level call to Ollama vision model.

    Uses the /api/generate endpoint with an 'images' field
    containing base64-encoded image data.

    HARDNING BASE:
    - Uses OLLAMA_REQUEST_TIMEOUT_SECONDS for HTTP timeout.
    """
    if not VISION_ENABLED:
        return "Vision is disabled in config (VISION_ENABLED = False)."

    if model_name is None:
        model_name = VISION_MODEL_NAME

    if not image_bytes:
        return "(No image data provided to vision model.)"

    img_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "images": [img_b64],
    }

    resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return (resp.json().get("response") or "").strip()


def run_vision(
    image_bytes: bytes,
    user_prompt: str,
    mode: str = "auto",
    model_name: Optional[str] = None,
) -> str:
    """
    High-level vision entrypoint.

    Parameters:
      image_bytes: raw bytes of the uploaded image
      user_prompt: user's instruction (may be empty)
      mode: one of "auto", "describe", "ocr", "code", "debug"
      model_name: optional override

    Output: plain text only (no markdown fences).

    HARDNING BASE:
    - Protected by a semaphore for concurrency control.
    - Timing + status logged to history.
    - Stage-level timeout wrapper + input/output size guards.
    - Graceful fallback on errors instead of raising.
    """
    if not image_bytes:
        return "(No image uploaded.)"

    mode = (mode or "auto").lower()
    if mode not in ("auto", "describe", "ocr", "code", "debug"):
        mode = "auto"

    base_instruction = """
You are a visual AI assistant running locally.
You can see one image and the user's text prompt.

General rules:
- Respond in plain text only. No markdown fences.
- Be concise but clear.
- If the user is a developer (logs, code, UI), focus on actionable insight.
""".strip()

    if mode == "describe":
        task = "Describe the image in detail: structure, objects, relationships, notable features."
    elif mode == "ocr":
        task = "Extract all text from the image (OCR). Preserve line structure if possible."
    elif mode == "code":
        task = (
            "Explain the image from a developer's viewpoint. If it shows code, UI, logs, or an error, "
            "focus on what it means and how to fix or improve it."
        )
    elif mode == "debug":
        task = (
            "Diagnose problems shown in the image (errors, broken UI, logs). "
            "Explain likely causes and concrete fixes."
        )
    else:  # auto
        task = (
            "Decide the best way to help based on the image and user prompt. "
            "You may describe, extract text, or debug as appropriate."
        )

    uprompt = user_prompt.strip() if user_prompt else ""
    if not uprompt:
        uprompt = "Describe this image in detail."
    uprompt = _sanitize_input_text(uprompt)

    final_prompt = f"""
{base_instruction}

Task mode: {mode}
Task description: {task}

User prompt:
{uprompt}
""".strip()

    # Timing + concurrency guard around the actual model call
    start = time.monotonic()
    status = "ok"
    error_msg: str | None = None
    effective_model = model_name or VISION_MODEL_NAME

    _VISION_SEMAPHORE.acquire()
    try:
        def _call():
            return call_ollama_vision(
                image_bytes=image_bytes,
                prompt=final_prompt,
                model_name=model_name,
            )

        result = _run_with_timeout(_call, "vision", effective_model)
        return _clamp_output_text(result)
    except Exception as e:
        status = "error"
        # Limit error length a bit before logging / returning
        error_msg = _truncate_with_notice(str(e), 600, "Error")
        fallback = f"Vision stage failed: {error_msg}"
        return _clamp_output_text(fallback)
    finally:
        duration = time.monotonic() - start
        _log_timing("vision", effective_model, duration, status, error_msg)
        _VISION_SEMAPHORE.release()
