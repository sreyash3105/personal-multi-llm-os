from __future__ import annotations

"""
chat_pipeline.py

Smart chat pipeline for the Personal Local AI OS.

NORMAL CHAT (handled in chat_ui.py):
    - Single model call using CHAT_MODEL_NAME (or overrides)

SMART CHAT (this file):
    - Uses SMART_CHAT_MODEL_NAME
    - Stages:
        1) Planner   -> builds a short JSON plan + notes
        2) Answer    -> uses plan + conversation (+ optional profile context) to generate response
        3) Judge     -> lightweight self-check (confidence + conflict + summary)
    - Logs stage timings via history_logger as pipeline_timing records.
    - UPDATED: Now logs full 'trace' (Plan -> Answer -> Judge) to history for the Dashboard.
"""

import json
import time
import threading
from typing import Any, Dict, List, Optional

from backend.core.config import (
    SMART_CHAT_MODEL_NAME,
    MAX_CONCURRENT_HEAVY_REQUESTS,
    OLLAMA_REQUEST_TIMEOUT_SECONDS,
)
from backend.modules.code.prompts import CHAT_SYSTEM_PROMPT
from backend.modules.code.pipeline import call_ollama
from backend.modules.telemetry.history import history_logger
from backend.modules.common.timeout_policy import run_with_retries
from backend.modules.jobs.queue_manager import (
    enqueue_job,
    try_acquire_next_job,
    get_job,
    mark_job_done,
    mark_job_failed,
)


# =========================
# Concurrency + timing
# =========================

_SMART_CHAT_SEMAPHORE = threading.BoundedSemaphore(value=MAX_CONCURRENT_HEAVY_REQUESTS)

# Simple, chat-specific retry policy (can be moved to config later)
_CHAT_MAX_RETRIES = 1           # total attempts = 2 (initial + 1 retry)
_CHAT_RETRY_BASE_DELAY_S = 1.0  # seconds


def _log_chat_timing(
    stage: str,
    model_name: str,
    duration_s: float,
    status: str,
    error: Optional[str] = None,
) -> None:
    """
    Best-effort timing logger for smart-chat stages.
    Shows up in the dashboard as 'pipeline_timing'.
    """
    try:
        if history_logger:
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
        # Must never break chat.
        pass


def _run_with_timeout(fn, stage: str, model_name: str):
    """
    Stage-level timeout + retry wrapper for planner / answer / judge.
    """
    start = time.monotonic()
    status = "ok"
    error_text: Optional[str] = None

    try:
        result = run_with_retries(
            fn=fn,
            label=stage,
            max_retries=_CHAT_MAX_RETRIES,
            base_delay_s=_CHAT_RETRY_BASE_DELAY_S,
            timeout_s=OLLAMA_REQUEST_TIMEOUT_SECONDS,
            timing_cb=None,          # chat logs aggregate timing itself
            is_retryable_error=None, # use default heuristic
        )
        return result
    except Exception as exc:
        status = "error"
        error_text = str(exc) or exc.__class__.__name__
        raise
    finally:
        duration = time.monotonic() - start
        _log_chat_timing(stage, model_name, duration, status, error_text)


# =========================
# Prompt helpers
# =========================

def _render_message_for_prompt(msg: Dict[str, Any]) -> str:
    """
    Render a stored chat message into a compact text line for the LLM prompt.
    """
    role = (msg.get("role") or "user").upper()
    text = msg.get("text") or ""

    if text.startswith("__IMG__"):
        lines = text.splitlines()
        caption = ""
        if len(lines) > 1:
            caption = "\n".join(lines[1:]).strip()
        if caption:
            return "%s (image): (caption: %s)" % (role, caption)
        return "%s (image): (no caption, image attached)" % role

    return "%s: %s" % (role, text)


def _build_conversation_block(messages: List[Dict[str, Any]], latest_user_text: str) -> str:
    """
    Build a conversation block for both planner and answer prompts.
    """
    convo_lines: List[str] = []
    for msg in messages:
        convo_lines.append(_render_message_for_prompt(msg))
    convo_lines.append("USER: %s" % latest_user_text)
    return "\n".join(convo_lines)


# =========================
# Lightweight judge for chat
# =========================

def _run_chat_judge(user_prompt: str, answer: str, model_name: str) -> Dict[str, Any]:
    """
    Lightweight judge for smart chat.
    """
    if not answer:
        return {
            "confidence_score": None,
            "conflict_score": None,
            "judgement_summary": "No answer to judge.",
            "raw_response": "",
            "parse_error": None,
        }

    judge_prompt = """
You are grading an AI chat assistant's reply.

You will see:
- USER_REQUEST: what the user asked.
- ASSISTANT_RESPONSE: what the assistant answered.

Your job:
1) Rate how confident you are that the answer is correct, helpful, and safe,
   as an integer 0–10 (higher = more confident).
2) Rate how likely it is that the answer is wrong, misleading, unsafe, or incomplete,
   as an integer 0–10 (higher = more problematic).
3) Write a short 1–3 sentence summary explaining your judgement.

Return STRICT JSON ONLY with this exact shape:

{
  "confidence_score": <int 0-10>,
  "conflict_score": <int 0-10>,
  "judgement_summary": "<short explanation>"
}

USER_REQUEST:
%s

ASSISTANT_RESPONSE:
%s

JSON:
""".strip() % (user_prompt, answer)

    raw_response = ""
    parse_error: Optional[str] = None
    confidence_score: Optional[int] = None
    conflict_score: Optional[int] = None
    summary = ""

    try:
        def _call():
            return call_ollama(judge_prompt, model_name).strip()

        raw_response = _run_with_timeout(_call, "chat_judge", model_name)
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
        parse_error = str(e)

    return {
        "confidence_score": confidence_score,
        "conflict_score": conflict_score,
        "judgement_summary": summary or "No structured summary available (chat judge).",
        "raw_response": raw_response,
        "parse_error": parse_error,
    }


# =========================
# Public entrypoint: smart chat pipeline
# =========================

def run_chat_smart(
    profile: Dict[str, Any],
    profile_id: str,
    chat_meta: Dict[str, Any],
    chat_id: str,
    messages: List[Dict[str, Any]],
    user_prompt: str,
    context_block: str = "",
) -> Dict[str, Any]:
    """
    SMART CHAT = planner → answer → judge
    
    Now includes full trace logging to history.
    """
    model_name = SMART_CHAT_MODEL_NAME
    convo_block = _build_conversation_block(messages, user_prompt)
    profile_name = profile.get("display_name") or profile_id

    # Normalize context string for safe embedding
    context_block = (context_block or "").strip()

    plan_text = ""
    planner_raw = ""
    planner_error: Optional[str] = None

    answer_text = ""
    answer_error: Optional[str] = None

    # ------------- Queue integration (per-profile) -------------
    job = enqueue_job(
        profile_id=profile_id,
        kind="chat_smart",
        meta={
            "chat_id": chat_id,
            "profile_name": profile_name,
        },
    )

    acquired = try_acquire_next_job(profile_id)
    if not acquired or acquired.id != job.id:
        start_wait = time.time()
        max_wait = 300.0  # 5 minutes timeout
        while time.time() - start_wait < max_wait:
            snapshot = get_job(job.id)
            if snapshot is None:
                answer_text = "(This smart chat job was cancelled or lost in the queue.)"
                answer_error = "queue_lost_job"
                break
            if snapshot.state == "running":
                break
            if snapshot.state in ("done", "failed", "cancelled"):
                answer_text = "(This smart chat job was already finished in another worker.)"
                answer_error = "queue_job_already_finished"
                break
            time.sleep(0.1)
        else:
            # Timeout reached
            answer_text = "(This smart chat job timed out waiting in queue.)"
            answer_error = "queue_timeout"
            time.sleep(0.05)

    if answer_error:
        try:
            mark_job_failed(job.id, answer_error)
        except Exception:
            pass
        # Even on error, we log what we have so far
        if history_logger:
            history_logger.log({
                "mode": "chat_smart",
                "status": "error",
                "original_prompt": user_prompt,
                "final_output": answer_text,
                "error": answer_error
            })
        
        return {
            "answer": answer_text,
            "plan": "",
            "judge": {},
            "model_used": model_name,
            "planner_error": None,
            "answer_error": answer_error,
        }

    # ------------- Planner + Answer (under semaphore) -------------
    _SMART_CHAT_SEMAPHORE.acquire()
    try:
        # ----- Planner stage -----
        planner_prompt = """
%s

You are the PLANNING module for a local developer assistant.

You will see:
- The current profile name.
- Optional profile knowledge notes (saved by the user).
- The recent conversation between USER and ASSISTANT.
- The user's latest request.

Your job:
1) Understand what the user is trying to achieve.
2) Produce a short plan (4–8 bullet points or steps) describing how the assistant
   should respond and structure the answer.
3) Call out any important risks, unknowns, or required clarifications.

Return STRICT JSON ONLY:

{
  "title": "<short 3-5 word title of the plan>",
  "plan": "<short stepwise plan>",
  "notes": "<risks / unknowns / extra thoughts>"
}

Current profile: %s

Profile knowledge (saved notes, may be empty):
%s

Conversation so far:
%s

LATEST USER REQUEST:
%s

JSON:
""".strip() % (
            CHAT_SYSTEM_PROMPT,
            profile_name,
            (context_block or "(none)"),
            convo_block,
            user_prompt,
        )

        try:
            def _call_planner():
                return call_ollama(planner_prompt, model_name).strip()

            planner_raw = _run_with_timeout(_call_planner, "chat_planner", model_name)
            candidate = planner_raw
            if "{" in candidate and "}" in candidate:
                candidate = candidate[candidate.find("{"): candidate.rfind("}") + 1]
            data = json.loads(candidate)
            
            # Extract structured plan data
            plan_title = str(data.get("title") or "Chat Response Plan").strip()
            plan_steps = str(data.get("plan") or "").strip()
            notes_text = str(data.get("notes") or "").strip()
            
            # Format plan for the Answer model
            plan_text = plan_steps
            if notes_text:
                plan_text = (plan_text + "\n\nNotes:\n" + notes_text).strip()
                
        except Exception as e:
            planner_error = str(e)
            plan_text = planner_raw or ""
            plan_title = "Planner Error"

        if not plan_text:
            plan_text = "No structured plan available. Respond as helpfully as possible."

        # ----- Answer stage -----
        answer_prompt = """
%s

You are in SMART mode.

You will see:
- The recent conversation.
- The user's latest request.
- Optional profile knowledge notes.
- A high-level plan that was generated for how to answer.

Use the plan as an internal guide, but:
- Do NOT repeat it step by step unless the user asked for a plan.
- Focus on a clear, helpful, technically sound answer.
- You may mention next steps or TODOs if useful.

Current profile: %s

Profile knowledge (saved notes, may be empty):
%s

Conversation so far:
%s

Latest user request:
USER: %s

High-level plan (for you, do not over-explain this plan unless it helps):
%s

ASSISTANT:
""".strip() % (
            CHAT_SYSTEM_PROMPT,
            profile_name,
            (context_block or "(none)"),
            convo_block,
            user_prompt,
            plan_text,
        )

        try:
            def _call_answer():
                return call_ollama(answer_prompt, model_name).strip()

            answer_text = _run_with_timeout(_call_answer, "chat_smart", model_name)
            if not answer_text:
                answer_error = "Empty answer from model."
        except Exception as e:
            answer_error = str(e)
            # Last-resort fallback
            fallback_prompt = f"""{CHAT_SYSTEM_PROMPT}\n\nUSER: {user_prompt}\n\nASSISTANT:"""
            try:
                answer_text = call_ollama(fallback_prompt, model_name).strip()
            except Exception:
                if not answer_text:
                    answer_text = "(Smart chat failed to generate a response.)"

    finally:
        _SMART_CHAT_SEMAPHORE.release()

    # ------------- Judge stage (outside semaphore) -------------
    judge_payload = _run_chat_judge(user_prompt=user_prompt, answer=answer_text, model_name=model_name)

    # Mark job done / failed in the queue
    try:
        if answer_error:
            mark_job_failed(job.id, answer_error)
        else:
            mark_job_done(job.id, note="chat_smart completed")
    except Exception:
        pass

    # =========================================================
    # 🟢 NEW: Log full Trace to History (Planner -> Answer -> Judge)
    # =========================================================
    if history_logger:
        trace_payload = {
            "planner": {
                "title": plan_title if 'plan_title' in locals() else "Smart Chat Plan",
                "content": plan_text,
                "confidence": 1.0, # Placeholder, smart chat planner implies confidence
                "error": planner_error
            },
            "worker": [
                {
                    "step": "response_generation",
                    "result": answer_text,
                    "error": answer_error
                }
            ],
            "risk_assessment": {
                "risk_level": 1.0, 
                "reason": "Chat mode (text generation only)",
                "tags": ["chat"]
            },
            "judge": judge_payload
        }
        
        history_logger.log({
            "mode": "chat_smart",
            "original_prompt": user_prompt,
            "final_output": answer_text,
            "trace": trace_payload,
            "risk": {"risk_level": 1.0}, # top-level summary for dashboard list
            "chat_id": chat_id,
            "profile_id": profile_id
        })
    # =========================================================

    return {
        "answer": answer_text,
        "plan": plan_text,
        "judge": judge_payload,
        "model_used": model_name,
        "planner_error": planner_error,
        "answer_error": answer_error,
    }