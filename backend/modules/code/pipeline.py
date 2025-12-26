"""
Core AI logic for the pipeline.
UPDATED: Integrated Job Queue to manage VRAM usage and serialize requests.
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
from backend.modules.telemetry.risk import assess_risk

# 🟢 NEW: Import Queue Manager
from backend.modules.jobs.queue_manager import (
    enqueue_job,
    try_acquire_next_job,
    get_job,
    mark_job_done,
    mark_job_failed,
)

# =========================
# Size guards (input / output)
# =========================

MAX_INPUT_CHARS = 8000
MAX_OUTPUT_CHARS = 12000


def _sanitize_input_text(text: Any) -> str:
    if text is None: return ""
    if not isinstance(text, str): text = str(text)
    if len(text) <= MAX_INPUT_CHARS: return text
    return text[: MAX_INPUT_CHARS - 200] + "\n\n[Truncated]"

def _clamp_output_text(text: Any) -> str:
    if text is None: return ""
    if not isinstance(text, str): text = str(text)
    if len(text) <= MAX_OUTPUT_CHARS: return text
    return text[: MAX_OUTPUT_CHARS - 200] + "\n\n[Output Truncated]"

# =========================
# Low-level Ollama call
# =========================

def call_ollama(prompt: str, model_name: str) -> str:
    url = f"{OLLAMA_URL}/api/generate"
    payload = {"model": model_name, "prompt": prompt, "stream": False}
    resp = requests.post(url, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json().get("response", "") or ""

# =========================
# Concurrency guard
# =========================

_HEAVY_SEMAPHORE = threading.BoundedSemaphore(value=MAX_CONCURRENT_HEAVY_REQUESTS)
_PROFILE_LOCKS: Dict[str, threading.Lock] = {}
_PROFILE_LOCKS_LOCK = threading.Lock()

def _get_profile_lock(profile_id: Optional[str]) -> Optional[threading.Lock]:
    if not profile_id: return None
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
    try:
        if history_logger:
            history_logger.log({
                "kind": "pipeline_timing",
                "stage": stage,
                "model": model_name,
                "duration_s": round(float(duration_s), 3),
                "status": status,
                "error": error,
            })
    except Exception:
        pass

def _run_with_timeout(fn, stage: str, model_name: str):
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
    if not raw_prompt: return DEFAULT_MODE, ""
    text = str(raw_prompt).replace("\r\n", "\n").strip()
    if not text: return DEFAULT_MODE, ""
    lines = text.split("\n", 1)
    first_line = lines[0].strip()
    rest = lines[1] if len(lines) > 1 else ""

    if first_line.startswith("///raw"): return "code_raw", rest.strip()
    if first_line.startswith("///review-only"): return "review_only", rest.strip()
    if first_line.startswith("///ctx") or first_line.startswith("///continue"): return "code_reviewed_ctx", rest.strip()

    return DEFAULT_MODE, _sanitize_input_text(text)

def extract_study_style_and_prompt(raw_prompt: str) -> Tuple[str, str]:
    """
    Extract study style and prompt from raw user input.

    Supported styles: normal, short, deep, quiz
    Default style: normal

    Format: First line can specify style like "style: deep" or just the prompt.
    """
    if not raw_prompt: return "normal", ""
    text = str(raw_prompt).replace("\r\n", "\n").strip()
    if not text: return "normal", ""

    lines = text.split("\n", 1)
    first_line = lines[0].strip().lower()
    rest = lines[1] if len(lines) > 1 else ""

    # Check for style specification in first line
    if first_line.startswith("style:"):
        style_part = first_line[6:].strip()
        if style_part in ["normal", "short", "deep", "quiz"]:
            # When style is specified, use the rest as the prompt (even if empty)
            return style_part, _sanitize_input_text(rest.strip())
        # Invalid style specified, fall back to normal with full text as prompt
        return "normal", _sanitize_input_text(text)

    # No style specified, use default with full text as prompt
    return "normal", _sanitize_input_text(text)

# =========================
# History context builder
# =========================

def build_history_context(max_items: int = 5) -> str:
    records = load_recent_records(limit=max_items)
    snippets = []
    for r in records:
        mode = r.get("mode", "")
        original = str(r.get("original_prompt") or "").strip()
        final = str(r.get("final_output") or "").strip()
        if not original and not final: continue
        snippets.append(f"Mode: {mode}\nUser prompt:\n{original}\n\nAssistant code:\n{final}")
    return "\n\n-----\n\n".join(snippets)

# =========================
# Stages
# =========================

def run_coder(user_prompt: str, profile_id: Optional[str] = None) -> str:
    user_prompt = _sanitize_input_text(user_prompt)
    coder_prompt = f"""
You are a code generation model.
Rules:
- Output ONLY runnable code.
- No markdown/backticks.
- No natural language explanation.

User request:
{user_prompt}
""".strip()
    
    start = time.monotonic()
    status, error_msg = "ok", None
    # Acquire semaphores BEFORE profile locks to prevent deadlock
    _HEAVY_SEMAPHORE.acquire()
    profile_lock = _get_profile_lock(profile_id)
    if profile_lock: profile_lock.acquire()
    try:
        def _call(): return call_ollama(coder_prompt, CODER_MODEL_NAME)
        return _clamp_output_text(_run_with_timeout(_call, "coder", CODER_MODEL_NAME))
    except Exception as e:
        status, error_msg = "error", str(e)
        return f"# Coder failed: {e}"
    finally:
        _log_timing("coder", CODER_MODEL_NAME, time.monotonic() - start, status, error_msg)
        if profile_lock: profile_lock.release()
        _HEAVY_SEMAPHORE.release()

def run_reviewer(original_prompt: str, draft_code: str, profile_id: Optional[str] = None) -> str:
    if not draft_code.strip(): return draft_code
    reviewer_prompt = f"""{REVIEWER_SYSTEM_PROMPT}\n\nUSER REQUEST:\n{original_prompt}\n\nDRAFT CODE:\n{draft_code}\n\nREVIEWED CODE:"""
    
    start = time.monotonic()
    status, error_msg = "ok", None
    # Acquire semaphores BEFORE profile locks to prevent deadlock
    _HEAVY_SEMAPHORE.acquire()
    profile_lock = _get_profile_lock(profile_id)
    if profile_lock: profile_lock.acquire()
    try:
        def _call(): return call_ollama(reviewer_prompt, REVIEWER_MODEL_NAME)
        return _clamp_output_text(_run_with_timeout(_call, "reviewer", REVIEWER_MODEL_NAME))
    except Exception as e:
        status, error_msg = "error", str(e)
        return f"# Reviewer failed: {e}\n{draft_code}"
    finally:
        _log_timing("reviewer", REVIEWER_MODEL_NAME, time.monotonic() - start, status, error_msg)
        if profile_lock: profile_lock.release()
        _HEAVY_SEMAPHORE.release()

def run_judge(original_prompt: str, coder_output: str, reviewer_output: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
    if not JUDGE_ENABLED:
        return {"confidence_score": 5.0, "conflict_score": 5.0, "judgement_summary": "Judge disabled"}

    start = time.monotonic()
    status, error_msg = "ok", None
    # Acquire semaphores BEFORE profile locks to prevent deadlock
    _HEAVY_SEMAPHORE.acquire()
    profile_lock = _get_profile_lock(profile_id)
    if profile_lock: profile_lock.acquire()
    try:
        judge_prompt = f"""{JUDGE_SYSTEM_PROMPT}

Original request:
{original_prompt}

Coder output:
{coder_output}

Reviewer output:
{reviewer_output}

Return JSON only:""".strip()

        def _call(): return call_ollama(judge_prompt, JUDGE_MODEL_NAME)
        raw = _run_with_timeout(_call, "judge", JUDGE_MODEL_NAME)

        # Robust JSON parsing with validation
        parsed_data = _parse_judge_response(raw)

        return parsed_data
    except Exception as e:
        status, error_msg = "error", str(e)
        return {"confidence_score": 0.0, "conflict_score": 0.0, "judgement_summary": f"Judge failed: {e}"}
    finally:
        _log_timing("judge", JUDGE_MODEL_NAME, time.monotonic() - start, status, error_msg)
        _HEAVY_SEMAPHORE.release()
        if profile_lock: profile_lock.release()


def _parse_judge_response(raw_response: str) -> Dict[str, Any]:
    """
    Robustly parse judge model response with comprehensive validation.

    Expected JSON structure:
    {
        "confidence_score": int (1-10),
        "conflict_score": int (1-10),
        "judgement_summary": str
    }

    Returns validated dict or raises exception for retry.
    """
    if not raw_response or not isinstance(raw_response, str):
        raise ValueError("Empty or invalid judge response")

    # Extract JSON candidate - improved version of naive slicing
    json_start = raw_response.find("{")
    json_end = raw_response.rfind("}") + 1

    if json_start == -1 or json_end <= json_start:
        raise ValueError(f"No valid JSON object found in response (length: {len(raw_response)})")

    json_candidate = raw_response[json_start:json_end]

    # Validate JSON is not too long (prevent memory exhaustion)
    if len(json_candidate) > 10000:  # 10KB limit
        raise ValueError(f"JSON candidate too large: {len(json_candidate)} characters")

    # Parse JSON with specific error handling
    try:
        data = json.loads(json_candidate)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in judge response: {e}") from e

    # Validate structure is a dict
    if not isinstance(data, dict):
        raise ValueError(f"Judge response is not a JSON object: {type(data)}")

    # Extract and validate required fields
    confidence_score = data.get("confidence_score")
    conflict_score = data.get("conflict_score")
    judgement_summary = data.get("judgement_summary")

    # Validate confidence_score
    if confidence_score is None:
        raise ValueError("Missing required field: confidence_score")
    try:
        confidence_score = int(confidence_score)
        if not (1 <= confidence_score <= 10):
            raise ValueError(f"confidence_score out of range (1-10): {confidence_score}")
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid confidence_score: {confidence_score} - {e}") from e

    # Validate conflict_score
    if conflict_score is None:
        raise ValueError("Missing required field: conflict_score")
    try:
        conflict_score = int(conflict_score)
        if not (1 <= conflict_score <= 10):
            raise ValueError(f"conflict_score out of range (1-10): {conflict_score}")
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid conflict_score: {conflict_score} - {e}") from e

    # Validate judgement_summary
    if judgement_summary is None:
        raise ValueError("Missing required field: judgement_summary")
    if not isinstance(judgement_summary, str):
        raise ValueError(f"judgement_summary is not a string: {type(judgement_summary)}")
    if len(judgement_summary) > 1000:  # Reasonable length limit
        judgement_summary = judgement_summary[:997] + "..."

    return {
        "confidence_score": float(confidence_score),
        "conflict_score": float(conflict_score),
        "judgement_summary": judgement_summary
    }

# =========================
# 🟢 UPDATED: MASTER PIPELINE with JOB QUEUE
# =========================

def run_smart_code_pipeline(user_prompt: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Runs the full Code Pipeline (Coder -> Reviewer -> Judge).
    MANAGED by Queue: Ensures only one heavy job per profile runs at a time.
    """
    
    # 1. Enqueue the Job
    job_profile = profile_id or "default"
    job = enqueue_job(profile_id=job_profile, kind="code_smart", meta={"prompt_len": len(user_prompt)})
    
    # 2. Wait for execution slot
    acquired = try_acquire_next_job(job_profile)
    if not acquired or acquired.id != job.id:
        # Wait in line...
        while True:
            snapshot = get_job(job.id)
            if snapshot is None or snapshot.state in ("failed", "cancelled"):
                return {"final_code": "", "judge": {}, "risk": {}, "error": "Job cancelled or failed in queue"}
            if snapshot.state == "running":
                break # It's our turn!
            time.sleep(0.1) # Poll interval

    try:
        # --- EXECUTION START ---
        
        # 1. Run Coder
        coder_out = run_coder(user_prompt, profile_id)
        
        # 2. Run Reviewer
        reviewer_out = run_reviewer(user_prompt, coder_out, profile_id)
        
        # 3. Run Judge
        judge_out = run_judge(user_prompt, coder_out, reviewer_out, profile_id)
        
        # 4. Assess Risk
        risk_out = assess_risk("code_generation", {"code": reviewer_out})

        # 5. Log Trace to History
        if history_logger:
            trace_payload = {
                "planner": {
                    "title": "Code Generation Plan",
                    "confidence": judge_out.get("confidence_score", 0),
                    "content": "1. Generate Draft (Coder)\n2. Refine & Fix (Reviewer)\n3. Verify Quality (Judge)"
                },
                "worker": [
                    {"step": "coder_draft", "result": coder_out[:200] + "...", "status": "ok"},
                    {"step": "reviewer_polish", "result": reviewer_out, "status": "ok"}
                ],
                "risk_assessment": risk_out,
                "judge": judge_out
            }
            
            history_logger.log({
                "mode": "code_smart",
                "original_prompt": user_prompt,
                "final_output": reviewer_out,
                "trace": trace_payload,
                "risk": risk_out,
                "profile_id": profile_id
            })

        mark_job_done(job.id)
        return {
            "final_code": reviewer_out,
            "judge": judge_out,
            "risk": risk_out
        }
        
    except Exception as e:
        mark_job_failed(job.id, str(e))
        return {"final_code": f"# Pipeline Error: {e}", "judge": {}, "risk": {}, "error": str(e)}

def run_study(user_prompt: str, style: str = "normal") -> str:
    """
    Run study/tutoring mode with the specified style.

    Args:
        user_prompt: The topic or question to study
        style: Teaching style - "normal", "short", "deep", or "quiz"

    Returns:
        Educational response from the study model
    """
    # Input validation
    if not user_prompt or not isinstance(user_prompt, str):
        return "Error: Empty or invalid study prompt provided"

    if style not in ["normal", "short", "deep", "quiz"]:
        return f"Error: Invalid style '{style}'. Supported styles: normal, short, deep, quiz"

    # Sanitize input
    user_prompt = _sanitize_input_text(user_prompt)

    # Build the study prompt with system instructions and style context
    study_prompt = f"""{STUDY_SYSTEM_PROMPT}

Style requested: {style}

User question/topic:
{user_prompt}

Please provide your educational response in the requested style.""".strip()

    # Use concurrency guards and timing like other pipeline functions
    start = time.monotonic()
    status, error_msg = "ok", None
    profile_lock = _get_profile_lock(None)  # Study doesn't use profile-specific locking
    if profile_lock: profile_lock.acquire()
    _HEAVY_SEMAPHORE.acquire()

    try:
        def _call(): return call_ollama(study_prompt, STUDY_MODEL_NAME)
        result = _clamp_output_text(_run_with_timeout(_call, "study", STUDY_MODEL_NAME))
        return result
    except Exception as e:
        status, error_msg = "error", str(e)
        return f"Study failed: {e}"
    finally:
        _log_timing("study", STUDY_MODEL_NAME, time.monotonic() - start, status, error_msg)
        _HEAVY_SEMAPHORE.release()
        if profile_lock: profile_lock.release()