"""
Core AI logic for the pipeline:
- low-level Ollama calls
- coder stage
- reviewer stage
- judge stage (confidence/conflict scoring)
- study stage (teaching / explanation / quizzes)
- mode parsing (///raw, ///review-only, ///ctx, ///continue)
- building context from history when requested

HARDENING BASE · V3.4:
- Simple concurrency guard for heavy stages (coder/reviewer/judge).
- Optional per-profile soft lock (serializes heavy work per profile when provided).
- Stage-level timeouts using OLLAMA_REQUEST_TIMEOUT_SECONDS.
- Input/output size guards to avoid huge payloads.
- Logs timing + status for each stage via history_logger.
"""

import json
import time
import threading
import concurrent.futures
from typing import Any, Dict, Optional, Tuple

import requests

from config import (
    OLLAMA_URL,
    CODER_MODEL_NAME,
    REVIEWER_MODEL_NAME,
    REQUEST_TIMEOUT,  # kept for compatibility; not used directly
    DEFAULT_MODE,
    JUDGE_MODEL_NAME,
    JUDGE_ENABLED,
    STUDY_MODEL_NAME,
    OLLAMA_REQUEST_TIMEOUT_SECONDS,
    MAX_CONCURRENT_HEAVY_REQUESTS,
)
from prompts import REVIEWER_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT, STUDY_SYSTEM_PROMPT
from history import load_recent_records, history_logger


# =========================
# Size guards (input / output)
# =========================

MAX_INPUT_CHARS = 8000
MAX_OUTPUT_CHARS = 12000


def _sanitize_input_text(text: Any) -> str:
    """
    Guardrail for incoming user text before building prompts.
    """
    if not isinstance(text, str):
        text = str(text or "")
    if len(text) <= MAX_INPUT_CHARS:
        return text
    head = text[:MAX_INPUT_CHARS]
    return head + "\n\n[Input truncated for safety — original content was too long.]"


def _clamp_output_text(text: Any) -> str:
    """
    Guardrail for model outputs before they propagate further.
    """
    if not isinstance(text, str):
        text = str(text or "")
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    head = text[:MAX_OUTPUT_CHARS]
    return head + "\n\n[Output truncated — response shortened to avoid overload.]"


# =========================
# Concurrency guard (heavy stages)
# =========================

_HEAVY_SEMAPHORE = threading.BoundedSemaphore(value=MAX_CONCURRENT_HEAVY_REQUESTS)

_PROFILE_LOCKS: Dict[str, threading.Lock] = {}
_PROFILE_LOCKS_MUTEX = threading.Lock()


def _get_profile_lock(profile_id: Optional[str]) -> Optional[threading.Lock]:
    """
    Returns a dedicated lock for the given profile_id.

    If profile_id is None or empty, no lock is used and the heavy semaphore alone
    provides coarse-grained concurrency control.
    """
    if not profile_id:
        return None
    with _PROFILE_LOCKS_MUTEX:
        lock = _PROFILE_LOCKS.get(profile_id)
        if lock is None:
            lock = threading.Lock()
            _PROFILE_LOCKS[profile_id] = lock
        return lock


def _log_timing(stage: str, model_name: str, duration_s: float, status: str, error: Optional[str] = None) -> None:
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
    Stage-level timeout wrapper.

    Even though call_ollama already uses an HTTP timeout, this
    ensures the stage itself is bounded and cannot hang indefinitely
    if something goes wrong beneath requests.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        return future.result(timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS)


# =========================
# Low-level model call
# =========================

def call_ollama(prompt: str, model_name: str) -> str:
    """
    Basic Ollama call wrapper.

    Uses OLLAMA_REQUEST_TIMEOUT_SECONDS for HTTP timeout.
    Caller is responsible for stage-level timeout and size clamping.
    """
    payload = {"model": model_name, "prompt": prompt, "stream": False}
    resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return (resp.json().get("response") or "").strip()


# =========================
# History-based context
# =========================

def build_history_context(max_items: int = 5) -> str:
    """
    Load recent interactions from history and turn them into a compact
    textual context that can be prepended to a new request.
    """
    records = load_recent_records(max_items)
    if not records:
        return ""

    snippets = []
    for rec in records:
        user = rec.get("normalized_prompt") or rec.get("original_prompt") or ""
        final = rec.get("final_output") or ""
        if not (user or final):
            continue

        snippets.append(
            "User request:\n"
            + str(user).strip()
            + "\n\nAssistant code:\n"
            + str(final).strip()
        )

    if not snippets:
        return ""

    return "\n\n-----\n\n".join(snippets)


# =========================
# Coder stage
# =========================

def run_coder(user_prompt: str, profile_id: Optional[str] = None) -> str:
    """
    First stage: generate draft code from the user's prompt.
    Uses CODER_MODEL_NAME.

    Guardrails:
    - Protected by heavy-semaphore.
    - Serialized per profile when profile_id is provided.
    - Stage-level timeout + fallback.
    - Input and output are size-guarded.
    """
    user_prompt = _sanitize_input_text(user_prompt)

    coder_prompt = f"""
You are a code generation model.

Rules:
- Output ONLY runnable code.
- Do NOT include any explanation, description, or natural language.
- Do NOT use markdown or triple backticks.
- Do NOT add docstrings or comments unless the user explicitly asks for them.
- If the user asks for an explanation, put it in comments inside the code, not outside.

User request:
{user_prompt}
""".strip()

    start = time.monotonic()
    status = "ok"
    error_msg: Optional[str] = None

    profile_lock = _get_profile_lock(profile_id)

    if profile_lock:
        profile_lock.acquire()
    _HEAVY_SEMAPHORE.acquire()
    try:
        def _call():
            return call_ollama(coder_prompt, CODER_MODEL_NAME)

        result = _run_with_timeout(_call, "coder", CODER_MODEL_NAME)
        result = _clamp_output_text(result)
        return result
    except Exception as e:
        status = "error"
        error_msg = str(e)
        fallback = f"# Coder stage failed: {error_msg}"
        return _clamp_output_text(fallback)
    finally:
        duration = time.monotonic() - start
        _log_timing("coder", CODER_MODEL_NAME, duration, status, error_msg)
        _HEAVY_SEMAPHORE.release()
        if profile_lock:
            profile_lock.release()


# =========================
# Reviewer stage
# =========================

def run_reviewer(original_prompt: str, draft_code: str, profile_id: Optional[str] = None) -> str:
    """
    Second stage: review and improve the draft code.
    Uses REVIEWER_MODEL_NAME.

    Guardrails:
    - Protected by heavy-semaphore.
    - Serialized per profile when profile_id is provided.
    - Stage-level timeout + fallback.
    - Input and output are size-guarded.
    """
    if not draft_code.strip():
        return draft_code

    original_prompt = _sanitize_input_text(original_prompt)
    draft_code = _sanitize_input_text(draft_code)

    reviewer_prompt = f"""{REVIEWER_SYSTEM_PROMPT}

Original request:
{original_prompt}

Draft code:
{draft_code}

Return ONLY the final improved code (no markdown fences, no explanations):
"""

    start = time.monotonic()
    status = "ok"
    error_msg: Optional[str] = None

    profile_lock = _get_profile_lock(profile_id)

    if profile_lock:
        profile_lock.acquire()
    _HEAVY_SEMAPHORE.acquire()
    try:
        def _call():
            return call_ollama(reviewer_prompt, REVIEWER_MODEL_NAME).strip()

        reviewed = _run_with_timeout(_call, "reviewer", REVIEWER_MODEL_NAME)
        reviewed = _clamp_output_text(reviewed or draft_code)
        return reviewed or draft_code
    except Exception as e:
        status = "error"
        error_msg = str(e)
        return _clamp_output_text(draft_code)
    finally:
        duration = time.monotonic() - start
        _log_timing("reviewer", REVIEWER_MODEL_NAME, duration, status, error_msg)
        _HEAVY_SEMAPHORE.release()
        if profile_lock:
            profile_lock.release()


# =========================
# Judge stage
# =========================

def run_judge(original_prompt: str, coder_output: str, reviewer_output: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Third stage: judge the answer for confidence and conflict.

    Returns a dict with:
        confidence_score, conflict_score, judgement_summary,
        raw_response, parse_error
    """
    if not JUDGE_ENABLED:
        return {
            "confidence_score": None,
            "conflict_score": None,
            "judgement_summary": "Judge disabled.",
            "raw_response": "",
            "parse_error": None,
        }

    original_prompt = _sanitize_input_text(original_prompt)
    coder_output = _sanitize_input_text(coder_output)
    reviewer_output = _sanitize_input_text(reviewer_output)

    judge_input = f"""
SYSTEM_PROMPT:
{JUDGE_SYSTEM_PROMPT}

USER_REQUEST:
{original_prompt}

CODER_OUTPUT:
{coder_output}

REVIEWER_OUTPUT:
{reviewer_output}
""".strip()

    raw_response = ""
    parse_error: Optional[str] = None
    confidence_score: Optional[int] = None
    conflict_score: Optional[int] = None
    summary = ""

    start = time.monotonic()
    status = "ok"
    error_msg: Optional[str] = None

    profile_lock = _get_profile_lock(profile_id)

    if profile_lock:
        profile_lock.acquire()
    _HEAVY_SEMAPHORE.acquire()
    try:
        def _call():
            return call_ollama(judge_input, JUDGE_MODEL_NAME).strip()

        raw_response = _run_with_timeout(_call, "judge", JUDGE_MODEL_NAME)
        raw_response = _clamp_output_text(raw_response)
        candidate = raw_response

        if "{" in candidate and "}" in candidate:
            candidate = candidate[candidate.find("{"): candidate.rfind("}") + 1]

        data = json.loads(candidate)

        if data.get("confidence_score") is not None:
            confidence_score = int(data.get("confidence_score"))
        if data.get("conflict_score") is not None:
            conflict_score = int(data.get("conflict_score"))

        summary = str(data.get("judgement_summary") or "").strip()

    except Exception as e:
        status = "error"
        error_msg = str(e)
        parse_error = str(e)
    finally:
        duration = time.monotonic() - start
        _log_timing("judge", JUDGE_MODEL_NAME, duration, status, error_msg)
        _HEAVY_SEMAPHORE.release()
        if profile_lock:
            profile_lock.release()

    return {
        "confidence_score": confidence_score,
        "conflict_score": conflict_score,
        "judgement_summary": summary or "No structured summary available.",
        "raw_response": raw_response,
        "parse_error": parse_error,
    }


# =========================
# Study mode helpers
# =========================

def extract_study_style_and_prompt(text: str) -> Tuple[str, str]:
    """
    For /api/study we support simple first-line tags:

    ///short  -> short explanation
    ///deep   -> deep dive explanation
    ///quiz   -> quiz mode
    (no tag) -> normal teaching mode
    """
    if not text:
        return "normal", ""

    stripped = text.lstrip()
    if not stripped.startswith("///"):
        return "normal", text.strip()

    lines = stripped.splitlines()
    first_line = lines[0].strip()
    rest = "\n".join(lines[1:]).strip()

    tag = first_line[3:].strip().lower()

    if tag in ("short", "brief"):
        return "short", rest
    if tag in ("deep", "dive", "detailed"):
        return "deep", rest
    if tag in ("quiz", "test"):
        return "quiz", rest

    return "normal", rest


def run_study(user_prompt: str, style: str = "normal") -> str:
    """
    Study / teaching stage: explanations, quizzes, etc.
    Uses STUDY_MODEL_NAME and STUDY_SYSTEM_PROMPT.
    """
    style = (style or "normal").lower()
    if style not in ("normal", "short", "deep", "quiz"):
        style = "normal"

    user_prompt = _sanitize_input_text(user_prompt)

    study_prompt = f"""
{STUDY_SYSTEM_PROMPT}

Requested style: {style}

User request / topic:
{user_prompt}
""".strip()

    start = time.monotonic()
    status = "ok"
    error_msg: Optional[str] = None

    try:
        def _call():
            return call_ollama(study_prompt, STUDY_MODEL_NAME)

        result = _run_with_timeout(_call, "study", STUDY_MODEL_NAME)
        return _clamp_output_text(result)
    except Exception as e:
        status = "error"
        error_msg = str(e)
        fallback = f"Study stage failed: {error_msg}"
        return _clamp_output_text(fallback)
    finally:
        duration = time.monotonic() - start
        _log_timing("study", STUDY_MODEL_NAME, duration, status, error_msg)


# =========================
# Tools runtime integration hooks (placeholder)
# =========================

def maybe_run_tool_call(model_response: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Placeholder hook for future tools integration.
    For now this function is a no-op and simply returns the original
    model response unchanged.
    """
    return model_response


# =========================
# Mode parsing (tags from laptop) for /api/code
# =========================

def extract_mode_and_prompt(text: str) -> Tuple[str, str]:
    """
    Supports special first-line tags for /api/code:

    ///raw          -> coder only (no reviewer)
    ///review-only  -> reviewer only (input is treated as draft code)
    ///ctx          -> coder -> reviewer WITH history context
    ///continue     -> same as ///ctx

    No tag         -> coder -> reviewer (default, with auto-escalation logic)
    """
    if not text:
        return DEFAULT_MODE, ""

    stripped = text.lstrip()
    if not stripped.startswith("///"):
        return DEFAULT_MODE, text.strip()

    lines = stripped.splitlines()
    first_line = lines[0].strip()
    rest = "\n".join(lines[1:]).strip()

    tag = first_line[3:].strip().lower()

    if tag in ("raw", "coder-only"):
        return "code_raw", rest
    if tag in ("review-only", "review"):
        return "review_only", rest
    if tag in ("ctx", "continue", "context"):
        return "code_reviewed_ctx", rest

    return DEFAULT_MODE, rest
