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
- Simple concurrency guard for heavy stages (coder/reviewer/judge/study).
- Optional per-profile soft lock (serializes heavy work per profile when provided).
- Stage-level timeouts using OLLAMA_REQUEST_TIMEOUT_SECONDS.
- Input/output size guards to avoid huge payloads.
- Logs timing + status for each stage via history_logger.
"""

from __future__ import annotations

import json
import time
import threading
from typing import Any, Dict, Optional, Tuple

import requests

from backend.core.config import (
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
from backend.modules.code.prompts import (
    REVIEWER_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    STUDY_SYSTEM_PROMPT,
)
from backend.modules.common.timeout_policy import run_with_retries
from backend.modules.telemetry.history import load_recent_records, history_logger


# =========================
# Size guards (input / output)
# =========================

MAX_INPUT_CHARS = 8000
MAX_OUTPUT_CHARS = 12000


def _sanitize_input_text(text: Any) -> str:
    """
    Guardrail for incoming user text before passing it into prompts.

    - Coerces non-str to str.
    - Truncates extremely long inputs, with a short notice appended.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    if len(text) <= MAX_INPUT_CHARS:
        return text

    head = text[: MAX_INPUT_CHARS - 200]
    notice = (
        "\n\n[Input truncated for safety — original prompt was too long. "
        "This may affect answer completeness.]"
    )
    return head + notice


def _clamp_output_text(text: Any) -> str:
    """
    Guardrail for outgoing model text before returning to callers.

    - Coerces non-str to str.
    - Truncates extremely long outputs, with a short notice appended.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    if len(text) <= MAX_OUTPUT_CHARS:
        return text

    head = text[: MAX_OUTPUT_CHARS - 200]
    notice = (
        "\n\n[Output truncated for safety — model tried to generate an extremely long answer. "
        "Some details may be missing.]"
    )
    return head + notice


# =========================
# Low-level Ollama call
# =========================

def call_ollama(prompt: str, model_name: str) -> str:
    """
    Low-level helper for calling Ollama.

    This is intentionally simple:
    - POSTs to /api/generate
    - Uses OLLAMA_REQUEST_TIMEOUT_SECONDS
    - Returns the 'response' text from the final chunk
    """
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
    }

    resp = requests.post(
        url,
        json=payload,
        timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()

    data = resp.json()
    return data.get("response", "") or ""


# =========================
# Concurrency guard (heavy stages)
# =========================

_HEAVY_SEMAPHORE = threading.BoundedSemaphore(value=MAX_CONCURRENT_HEAVY_REQUESTS)

# Optional per-profile soft locks for heavy work.
_PROFILE_LOCKS: Dict[str, threading.Lock] = {}
_PROFILE_LOCKS_LOCK = threading.Lock()


def _get_profile_lock(profile_id: Optional[str]) -> Optional[threading.Lock]:
    """
    Get or create a soft lock for a given profile.

    If profile_id is None or empty, returns None (no per-profile serialization).
    """
    if not profile_id:
        return None

    with _PROFILE_LOCKS_LOCK:
        lock = _PROFILE_LOCKS.get(profile_id)
        if lock is None:
            lock = threading.Lock()
            _PROFILE_LOCKS[profile_id] = lock
        return lock


# =========================
# Timing logs
# =========================

def _log_timing(stage: str, model_name: str, duration_s: float, status: str, error: Optional[str] = None) -> None:
    """
    Record a small timing record for the dashboard.

    kind: "pipeline_timing"
      - stage: "coder" | "reviewer" | "judge" | "study"
      - model: model name used
      - duration_s: float seconds
      - status: "ok" | "error" | "timeout"
      - error: optional error string
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
        # timing logs should never break the main flow
        pass


def _run_with_timeout(fn, stage: str, model_name: str):
    """
    Stage-level timeout + retry wrapper.

    Uses the shared timeout_policy.run_with_retries helper to ensure:
    - per-attempt timeout (OLLAMA_REQUEST_TIMEOUT_SECONDS)
    - bounded retries with simple backoff
    - no behaviour change beyond "best-effort retry on transient failure".
    """
    # NOTE: Stage-level timing is still logged by the individual stage
    # functions (run_coder / run_reviewer / run_judge / run_study) via
    # _log_timing in their own try/finally blocks.
    return run_with_retries(
        fn=fn,
        label=stage,
        max_retries=1,
        base_delay_s=1.0,
        timeout_s=OLLAMA_REQUEST_TIMEOUT_SECONDS,
        timing_cb=None,
        is_retryable_error=None,
    )


# =========================
# Mode parsing
# =========================

def extract_mode_and_prompt(raw_prompt: str) -> Tuple[str, str]:
    """
    Parse the raw prompt to detect special modes.

    Recognized tags (prefix on the first line):
      - "///raw"           -> coder only, no reviewer
      - "///review-only"   -> reviewer only, treat prompt as code to review
      - "///ctx"           -> coder+reviewer with recent history context
      - "///continue"      -> same as ///ctx, meant for "continue previous"
      - default            -> coder+reviewer (no history context)

    Returns:
      mode, cleaned_prompt
    """
    if not raw_prompt:
        return DEFAULT_MODE, ""

    # Normalize newlines and strip leading/trailing whitespace
    text = str(raw_prompt).replace("\r\n", "\n").strip()
    if not text:
        return DEFAULT_MODE, ""

    lines = text.split("\n", 1)
    first_line = lines[0].strip()
    rest = lines[1] if len(lines) > 1 else ""

    mode = DEFAULT_MODE
    if first_line.startswith("///raw"):
        mode = "code_raw"
        cleaned = rest.strip()
    elif first_line.startswith("///review-only"):
        mode = "review_only"
        cleaned = rest.strip()
    elif first_line.startswith("///ctx") or first_line.startswith("///continue"):
        mode = "code_reviewed_ctx"
        cleaned = rest.strip()
    else:
        cleaned = text

    cleaned = _sanitize_input_text(cleaned)
    return mode, cleaned


def extract_study_style_and_prompt(raw_prompt: str) -> Tuple[str, str]:
    """
    Parse the raw prompt to determine the study style.

    Recognized tags (can be on their own line OR prefix on same line):
      - "///short"   -> short explanation
      - "///deep"    -> deep explanation
      - "///quiz"    -> quiz mode
      - default      -> normal explanation

    Examples:
      "///short Explain X"        -> style="short", prompt="Explain X"
      "///short\nExplain X"       -> style="short", prompt="Explain X"
    """
    if not raw_prompt:
        return "normal", ""

    text = str(raw_prompt).replace("\r\n", "\n").strip()
    if not text:
        return "normal", ""

    lines = text.split("\n")
    first_line = lines[0].strip()
    remaining_lines = lines[1:]

    def _strip_tag(tag: str) -> str:
        # Remove the tag from the first line and combine with remaining lines.
        # Handles both:
        #   "///short Explain X"
        #   "///short\nExplain X"
        content_on_first = first_line[len(tag):].strip()
        rest = "\n".join(remaining_lines).strip()
        if content_on_first and rest:
            combined = content_on_first + "\n" + rest
        elif content_on_first:
            combined = content_on_first
        else:
            combined = rest
        return combined.strip()

    style = "normal"
    cleaned = text

    if first_line.startswith("///short"):
        style = "short"
        cleaned = _strip_tag("///short")
    elif first_line.startswith("///deep"):
        style = "deep"
        cleaned = _strip_tag("///deep")
    elif first_line.startswith("///quiz"):
        style = "quiz"
        cleaned = _strip_tag("///quiz")
    else:
        cleaned = text

    cleaned = _sanitize_input_text(cleaned)
    return style, cleaned


# =========================
# History context builder
# =========================

def build_history_context(max_items: int = 5) -> str:
    """
    Build a short context block from recent history for the coder.

    This pulls from the 'history' database via load_recent_records and returns
    a compact text representation suitable for inclusion in prompts.
    """
    records = load_recent_records(limit=max_items)
    snippets = []

    for r in records:
        mode = r.get("mode", "")
        original = str(r.get("original_prompt") or "").strip()
        final = str(r.get("final_output") or "").strip()
        if not original and not final:
            continue

        snippet = (
            f"Mode: {mode}\n"
            + "User prompt:\n"
            + original
            + "\n\nAssistant code:\n"
            + str(final).strip()
        )

        snippets.append(snippet)

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
- If the user asks for an explanation, put it in comments inside
the code, not outside.

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

USER REQUEST:
{original_prompt}

DRAFT CODE:
{draft_code}

REVIEWED CODE (FINAL, IMPROVED, AND FIXED IF NEEDED):
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
            return call_ollama(reviewer_prompt, REVIEWER_MODEL_NAME)

        result = _run_with_timeout(_call, "reviewer", REVIEWER_MODEL_NAME)
        result = _clamp_output_text(result)
        return result
    except Exception as e:
        status = "error"
        error_msg = str(e)
        fallback = f"# Reviewer stage failed: {error_msg}\n\n# Original draft preserved below:\n{draft_code}"
        return _clamp_output_text(fallback)
    finally:
        duration = time.monotonic() - start
        _log_timing("reviewer", REVIEWER_MODEL_NAME, duration, status, error_msg)
        _HEAVY_SEMAPHORE.release()
        if profile_lock:
            profile_lock.release()


# =========================
# Judge stage
# =========================

def run_judge(
    original_prompt: str,
    coder_output: str,
    reviewer_output: str,
    profile_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Third stage: judge the answer for confidence and conflict.

    Returns a dict with:
        confidence_score, conflict_score, judgement_summary,
        raw_response, parse_error

    Scoring (float-based):
      - confidence_score: float 0.00–10.00 (higher = better)
      - conflict_score:   float 0.00–10.00 (higher = more problematic)
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

    judge_prompt = f"""{JUDGE_SYSTEM_PROMPT}

You will see:
- USER_REQUEST: what the user asked.
- CODER_ANSWER: the initial code from the fast coder.
- REVIEWER_ANSWER: the final code after the reviewer stage.

Your job:
1) Rate how confident you are that the FINAL answer is correct, safe, and useful,
   as a FLOAT in the range 0.00–10.00 (higher = better).
2) Rate how likely it is that the FINAL answer is wrong, misleading, unsafe, or incomplete,
   as a FLOAT in the range 0.00–10.00 (higher = more problematic).
3) Write a short 1–3 sentence explanation summarizing your judgement.

Return STRICT JSON ONLY, with NO extra commentary, in this exact shape:

{{
  "confidence_score": 8.75,
  "conflict_score": 2.50,
  "judgement_summary": "Very likely correct and safe; minor potential edge cases only."
}}

Rules:
- "confidence_score" MUST be a number (float), NOT a string.
- "conflict_score" MUST be a number (float), NOT a string.
- Do NOT include any extra keys or text outside the JSON object.

USER_REQUEST:
{original_prompt}

CODER_ANSWER:
{coder_output}

REVIEWER_ANSWER:
{reviewer_output}

JSON:
""".strip()

    def _to_float_score(val: Any) -> Optional[float]:
        """
        Best-effort conversion to a clamped float in [0.00, 10.00].
        Returns None if not parseable.
        """
        if val is None:
            return None
        try:
            f = float(val)
        except Exception:
            return None
        if f < 0.0:
            f = 0.0
        elif f > 10.0:
            f = 10.0
        return round(f, 2)

    start = time.monotonic()
    status = "ok"
    error_msg: Optional[str] = None

    profile_lock = _get_profile_lock(profile_id)

    if profile_lock:
        profile_lock.acquire()
    _HEAVY_SEMAPHORE.acquire()
    try:
        def _call():
            return call_ollama(judge_prompt, JUDGE_MODEL_NAME)

        raw = _run_with_timeout(_call, "judge", JUDGE_MODEL_NAME)
        raw = _clamp_output_text(raw)

        # Try to extract JSON if the model wrapped it in extra text
        candidate = raw
        if "{" in candidate and "}" in candidate:
            candidate = candidate[candidate.find("{"): candidate.rfind("}") + 1]

        data = json.loads(candidate)

        confidence_score = _to_float_score(data.get("confidence_score"))
        conflict_score = _to_float_score(data.get("conflict_score"))
        summary = str(data.get("judgement_summary") or "").strip()

        return {
            "confidence_score": confidence_score,
            "conflict_score": conflict_score,
            "judgement_summary": summary or "No structured summary provided by judge.",
            "raw_response": raw,
            "parse_error": None,
        }

    except Exception as e:
        status = "error"
        error_msg = str(e)
        return {
            "confidence_score": None,
            "conflict_score": None,
            "judgement_summary": "Judge failed.",
            "raw_response": "",
            "parse_error": str(e),
        }
    finally:
        duration = time.monotonic() - start
        _log_timing("judge", JUDGE_MODEL_NAME, duration, status, error_msg)
        _HEAVY_SEMAPHORE.release()
        if profile_lock:
            profile_lock.release()



# =========================
# Study / teaching stage
# =========================

def run_study(user_prompt: str, style: str = "normal") -> str:
    """
    Study / teaching helper.

    style:
      - "normal"
      - "short"
      - "deep"
      - "quiz"
    """
    user_prompt = _sanitize_input_text(user_prompt)

    style = (style or "normal").strip().lower()
    if style not in ("normal", "short", "deep", "quiz"):
        style = "normal"

    # We keep the prompt simple here, with style injected clearly.
    study_prompt = f"""{STUDY_SYSTEM_PROMPT}

STYLE: {style}

USER_REQUEST:
{user_prompt}
""".strip()

    start = time.monotonic()
    status = "ok"
    error_msg: Optional[str] = None

    _HEAVY_SEMAPHORE.acquire()
    try:
        def _call():
            return call_ollama(study_prompt, STUDY_MODEL_NAME)

        result = _run_with_timeout(_call, "study", STUDY_MODEL_NAME)
        result = _clamp_output_text(result)
        return result
    except Exception as e:
        status = "error"
        error_msg = str(e)
        fallback = f"(Study stage failed: {error_msg})"
        return _clamp_output_text(fallback)
    finally:
        duration = time.monotonic() - start
        _log_timing("study", STUDY_MODEL_NAME, duration, status, error_msg)
        _HEAVY_SEMAPHORE.release()
