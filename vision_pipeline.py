"""
Vision pipeline for the local AI assistant.

- Wraps a vision-capable Ollama model (e.g. llava:7b)
- Single entrypoint: run_vision(image_bytes, user_prompt, mode)

Separated from main code pipeline so code/study/chat don't depend on it.
"""

import base64
from typing import Optional

import requests

from config import OLLAMA_URL, VISION_MODEL_NAME, VISION_ENABLED, REQUEST_TIMEOUT


def call_ollama_vision(
    image_bytes: bytes,
    prompt: str,
    model_name: Optional[str] = None,
) -> str:
    """
    Low-level call to Ollama vision model.

    Uses the /api/generate endpoint with an 'images' field
    containing base64-encoded image data.
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
    High-level vision entrypoint.

    Parameters:
      image_bytes: raw bytes of the uploaded image
      user_prompt: user's instruction (may be empty)
      mode: one of "auto", "describe", "ocr", "code", "debug"
      model_name: optional override

    Output: plain text only (no markdown fences).
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

    final_prompt = f"""
{base_instruction}

Task mode: {mode}
Task description: {task}

User prompt:
{uprompt}
""".strip()

    return call_ollama_vision(image_bytes=image_bytes, prompt=final_prompt, model_name=model_name)
