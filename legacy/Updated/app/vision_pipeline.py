"""
Vision pipeline for the Local Personal AI OS.

Provides a single API-style function:
    run_vision(image_bytes, user_prompt, mode)

This isolates the vision logic from the main code pipeline and chat,
so everything stays modular.
"""

import base64
from typing import Optional
import requests

from config import (
    OLLAMA_URL,
    VISION_MODEL_NAME,
    VISION_ENABLED,
    REQUEST_TIMEOUT,
)


def call_ollama_vision(
    image_bytes: bytes,
    prompt: str,
    model_name: Optional[str] = None,
) -> str:
    """
    Low-level call to Ollama’s vision model via /api/generate
    using the base64 image field.
    """
    if not VISION_ENABLED:
        return "Vision is disabled in config."

    if model_name is None:
        model_name = VISION_MODEL_NAME

    if not image_bytes:
        return "(No image data received.)"

    img_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "images": [img_b64],
    }

    resp = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return (resp.json().get("response") or "").strip()


def run_vision(
    image_bytes: bytes,
    user_prompt: str,
    mode: str = "auto",
    model_name: Optional[str] = None,
) -> str:
    """
    High-level wrapper with different behaviors depending on the "mode".

    Modes:
      auto      -> decide based on image + prompt
      describe   -> explain in detail
      ocr        -> extract text
      code       -> explain from a developer’s viewpoint
      debug      -> detect issues and fixes
    """
    if not image_bytes:
        return "(No image uploaded.)"

    mode = (mode or "auto").lower()
    if mode not in ("auto", "describe", "ocr", "code", "debug"):
        mode = "auto"

    base_instruction = """
You are a local offline visual AI assistant.
You see the image and the user’s text prompt.

General rules:
- Plain text only (no markdown fences)
- Be concise but informative
- If showing logs/code/UI — focus on actionable insight
""".strip()

    if mode == "describe":
        task = "Describe the entire image in detail."
    elif mode == "ocr":
        task = "Extract all visible text from the image (OCR)."
    elif mode == "code":
        task = "Explain the image like a senior software engineer viewing UI/logs/code."
    elif mode == "debug":
        task = "Diagnose issues in the screenshot and propose concrete fixes."
    else:
        task = "Automatically decide the best kind of assistance."

    user = user_prompt.strip() if user_prompt else "Describe this image."

    final_prompt = f"""
{base_instruction}

Mode: {mode}
Task: {task}

User prompt:
{user}
""".strip()

    return call_ollama_vision(image_bytes, final_prompt, model_name=model_name)
