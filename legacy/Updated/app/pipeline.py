"""
Core AI logic for the pipeline:
- low-level Ollama calls
- coder stage
- reviewer stage
- judge stage (confidence / conflict scoring)
- study stage (teaching / quizzes)
- mode parsing (///raw, ///review-only, ///ctx, ///continue)
- history-aware context building
"""

import json
import requests

from config import (
    OLLAMA_URL,
    CODER_MODEL_NAME,
    REVIEWER_MODEL_NAME,
    REQUEST_TIMEOUT,
    DEFAULT_MODE,
    JUDGE_MODEL_NAME,
    JUDGE_ENABLED,
    STUDY_MODEL_NAME,
)
from prompts import REVIEWER_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT, STUDY_SYSTEM_PROMPT
from history import load_recent_records


# =========================
# Low-level model call
# =========================
def call_ollama(prompt: str, model_name: str) -> str:
    payload = {"model": model_name, "prompt": prompt, "stream": False}
    resp = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


# =========================
# History-based context
# =========================
def build_history_context(max_items: int = 5) -> str:
    """
    Load recent interactions and produce minimal prompt context.
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
            "User request:\n" + user.strip() +
            "\n\nAssistant code:\n" + final.strip()
        )

    if not snippets:
        return ""
    return "\n\n-----\n\n".join(snippets)


# =========================
# Coder stage
# =========================
def run_coder(user_prompt: str) -> str:
    coder_prompt = f"""
You are a code generation model.

Rules:
- Output ONLY runnable code.
- No explanations, markdown fences, or natural language.
- Comments ONLY if explicitly asked by the user.

User request:
{user_prompt}
""".strip()

    return call_ollama(coder_prompt, CODER_MODEL_NAME)


# =========================
# Reviewer stage
# =========================
def run_reviewer(original_prompt: str, draft_code: str) -> str:
    if not draft_code.strip():
        return draft_code

    reviewer_prompt = f"""{REVIEWER_SYSTEM_PROMPT}

Original request:
{original_prompt}

Draft code:
{draft_code}

Return ONLY improved final code (no markdown, no text outside code):
"""
    reviewed = call_ollama(reviewer_prompt, REVIEWER_MODEL_NAME).strip()
    return reviewed or draft_code


# =========================
# Judge stage
# =========================
def run_judge(original_prompt: str, coder_output: str, reviewer_output: str) -> dict:
    """
    Returns a safe parsed structure regardless of model response.
    """
    if not JUDGE_ENABLED:
        return {
            "confidence_score": None,
            "conflict_score": None,
            "judgement_summary": "Judge disabled.",
            "raw_response": "",
            "parse_error": None,
        }

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
    parse_error = None
    confidence_score = None
    conflict_score = None
    summary = ""

    try:
        raw_response = call_ollama(judge_input, JUDGE_MODEL_NAME).strip()
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
        "judgement_summary": summary or "No structured summary available.",
        "raw_response": raw_response,
        "parse_error": parse_error,
    }


# =========================
# Study mode
# =========================
def extract_study_style_and_prompt(text: str):
    if not text:
        return "normal", ""

    stripped = text.lstrip()
    if not stripped.startswith("///"):
        return "normal", text.strip()

    lines = stripped.splitlines()
    first = lines[0].strip()
    rest = "\n".join(lines[1:]).strip()
    tag = first[3:].strip().lower()

    if tag in ("short", "brief"):
        return "short", rest
    if tag in ("deep", "dive", "detailed"):
        return "deep", rest
    if tag in ("quiz", "test"):
        return "quiz", rest

    return "normal", rest


def run_study(user_prompt: str, style: str = "normal") -> str:
    if style not in ("normal", "short", "deep", "quiz"):
        style = "normal"

    study_prompt = f"""
{STUDY_SYSTEM_PROMPT}

Requested style: {style}

User request:
{user_prompt}
""".strip()

    return call_ollama(study_prompt, STUDY_MODEL_NAME)


# =========================
# Mode parsing (/api/code)
# =========================
def extract_mode_and_prompt(text: str):
    if not text:
        return DEFAULT_MODE, ""

    stripped = text.lstrip()
    if not stripped.startswith("///"):
        return DEFAULT_MODE, text.strip()

    lines = stripped.splitlines()
    first = lines[0].strip()
    rest = "\n".join(lines[1:]).strip()
    tag = first[3:].strip().lower()

    if tag in ("raw", "coder-only"):
        return "code_raw", rest
    if tag in ("review-only", "review"):
        return "review_only", rest
    if tag in ("ctx", "continue", "context"):
        return "code_reviewed_ctx", rest

    return DEFAULT_MODE, rest
