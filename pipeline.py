"""
Core AI logic for the pipeline:
- low-level Ollama calls
- coder stage
- reviewer stage
- judge stage (confidence/conflict scoring)
- study stage (teaching / explanation / quizzes)
- mode parsing (///raw, ///review-only, ///ctx, ///continue)
- building context from history when requested
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
            + user.strip()
            + "\n\nAssistant code:\n"
            + final.strip()
        )

    if not snippets:
        return ""

    return "\n\n-----\n\n".join(snippets)


# =========================
# Coder stage
# =========================

def run_coder(user_prompt: str) -> str:
    """
    First stage: generate draft code from the user's prompt.
    Uses CODER_MODEL_NAME.

    We enforce:
    - code-only output (as much as the model respects)
    """
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

    return call_ollama(coder_prompt, CODER_MODEL_NAME)


# =========================
# Reviewer stage
# =========================

def run_reviewer(original_prompt: str, draft_code: str) -> str:
    """
    Second stage: review and improve the draft code.
    Uses REVIEWER_MODEL_NAME.
    """
    if not draft_code.strip():
        return draft_code

    reviewer_prompt = f"""{REVIEWER_SYSTEM_PROMPT}

Original request:
{original_prompt}

Draft code:
{draft_code}

Return ONLY the final improved code (no markdown fences, no explanations):
"""
    reviewed = call_ollama(reviewer_prompt, REVIEWER_MODEL_NAME).strip()
    return reviewed or draft_code


# =========================
# Judge stage
# =========================

def run_judge(original_prompt: str, coder_output: str, reviewer_output: str) -> dict:
    """
    Third stage: judge the answer for confidence and conflict.

    Returns a dict like:
      {
        "confidence_score": int | None,
        "conflict_score": int | None,
        "judgement_summary": str,
        "raw_response": str,
        "parse_error": Optional[str],
      }

    This function is designed to be safe:
    - If JUDGE_ENABLED is False, it returns a neutral stub.
    - If the model returns invalid JSON, it captures parse_error
      but does not raise, so the main pipeline never breaks.
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

        # Try to trim to JSON segment if there is extra text around it
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
# Study mode helpers
# =========================

def extract_study_style_and_prompt(text: str):
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

    tag = first_line[3:].strip().lower()  # remove "///"

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

    study_prompt = f"""
{STUDY_SYSTEM_PROMPT}

Requested style: {style}

User request / topic:
{user_prompt}
""".strip()

    return call_ollama(study_prompt, STUDY_MODEL_NAME)

# =========================
# Tools runtime integration hooks (placeholder)
# =========================

def maybe_run_tool_call(model_response: str, context: dict | None = None) -> str:
    """
    Placeholder hook for future tools integration.

    For now this function is a no-op and simply returns the original
    model response unchanged. Future V3.x steps can:
      - inspect model_response for tool call directives
      - call into the tools_runtime module
      - merge tool outputs back into a final response

    Keeping this here avoids touching core endpoint logic until the
    tools runtime is fully ready and tested.
    """
    return model_response

# =========================
# Mode parsing (tags from laptop) for /api/code
# =========================

def extract_mode_and_prompt(text: str):
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

    tag = first_line[3:].strip().lower()  # remove "///"

    if tag in ("raw", "coder-only"):
        return "code_raw", rest
    if tag in ("review-only", "review"):
        return "review_only", rest
    if tag in ("ctx", "continue", "context"):
        return "code_reviewed_ctx", rest

    return DEFAULT_MODE, rest
