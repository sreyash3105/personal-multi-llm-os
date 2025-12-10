from __future__ import annotations

from typing import Tuple, Dict, Any
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.modules.code.pipeline import (
    run_coder,
    run_reviewer,
    run_judge,
    run_study,
    extract_mode_and_prompt,
    build_history_context,
    extract_study_style_and_prompt,
)
from backend.modules.telemetry.history import history_logger
from backend.core.config import (
    ESCALATION_ENABLED,
    ESCALATION_CONFIDENCE_THRESHOLD,
    ESCALATION_CONFLICT_THRESHOLD,
    VISION_ENABLED,
    CODER_MODEL_NAME,
    REVIEWER_MODEL_NAME,
    JUDGE_MODEL_NAME,
    JUDGE_ENABLED,
    STUDY_MODEL_NAME,
    VISION_MODEL_NAME,
    STT_ENABLED,       # 🟢 NEW
    STT_MODEL_NAME,    # 🟢 NEW
)
from backend.modules.telemetry.dashboard import render_dashboard, security_router
from backend.modules.vision.vision_pipeline import run_vision
from backend.modules.chat.chat_ui import router as chat_router
from backend.modules.tools.tools_runtime import execute_tool
from backend.modules.telemetry.risk import assess_risk
from backend.modules.security.security_sessions import create_security_session
from backend.modules.stt.stt_router import router as stt_router # 🟢 NEW
from backend.modules.router.api_router import router as intent_router
from backend.modules.automation.router import router as automation_router

# =========================
# FastAPI app
# =========================

app = FastAPI(title="Local Code, Study & Chat Assistant")

# Mount chat router (provides /api/chat*, including vision-in-chat)
app.include_router(chat_router)
app.include_router(stt_router)
# Mount security dashboard API router
app.include_router(security_router)
app.include_router(intent_router)
app.include_router(automation_router)
# =========================
# API models
# =========================

class CodeRequest(BaseModel):
    prompt: str


class CodeResponse(BaseModel):
    output: str


class StudyRequest(BaseModel):
    prompt: str


class StudyResponse(BaseModel):
    output: str


class VisionResponse(BaseModel):
    output: str

class STTResponse(BaseModel):
    text: str
    language: str | None = None

class ToolExecRequest(BaseModel):
    tool: str
    args: Dict[str, Any] | None = None


class ToolExecResponse(BaseModel):
    ok: bool
    tool: str
    result: Any | None = None
    error: str | None = None
    risk: Dict[str, Any] | None = None


# =========================
# Escalation helpers
# =========================

# =========================
# Escalation helpers
# =========================

def should_escalate(judge_result: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Decide whether to escalate based on judge scores.
    Returns (escalate: bool, reason: str).

    Scores expected on a 0.00–10.00 float scale:
      - confidence_score (lower → worse)
      - conflict_score   (higher → worse)
    """
    if not judge_result:
        return False, ""

    reasons: list[str] = []

    # Confidence threshold check
    cs = judge_result.get("confidence_score")
    try:
        if cs is not None:
            cs_val = float(cs)
            thresh = float(ESCALATION_CONFIDENCE_THRESHOLD)
            if cs_val < thresh:
                reasons.append(f"low confidence ({cs_val:.2f} < {thresh:.2f})")
    except Exception:
        # Parsing failed; ignore confidence dimension
        pass

    # Conflict threshold check
    cf = judge_result.get("conflict_score")
    try:
        if cf is not None:
            cf_val = float(cf)
            thresh = float(ESCALATION_CONFLICT_THRESHOLD)
            if cf_val > thresh:
                reasons.append(f"high conflict ({cf_val:.2f} > {thresh:.2f})")
    except Exception:
        # Parsing failed; ignore conflict dimension
        pass

    if not reasons:
        return False, ""

    return True, "; ".join(reasons)


def inject_escalation_comment(code: str, reason: str) -> str:
    """
    Add a comment at the top of the final code when escalation happened.
    Uses '#' because it's safe (shell/Python) and ignored by most languages.
    """
    if not code:
        return code

    reason = reason or "auto-escalated to heavy review"
    comment = f"# ESCALATION: {reason}"

    stripped = code.lstrip()
    if stripped.startswith(comment):
        return code

    # preserve original newlines
    return f"{comment}\n{code}"



# =========================
# /api/code endpoint
# =========================

@app.post("/api/code", response_model=CodeResponse)
def generate_code(req: CodeRequest):
    """
    Main endpoint used by the laptop client for coding tasks.

    Modes (from first line tags):

    - default (no tag):
        prompt -> fast coder [judge]
            -> direct final (if high confidence)
            -> OR escalate to reviewer (heavy) + comment

    - "///raw":
        prompt -> coder only -> final code

    - "///review-only":
        prompt (treated as draft code) -> reviewer only -> final code

    - "///ctx" or "///continue":
        (history context + current prompt)
          -> fast coder [judge]
          -> direct final or escalate to reviewer (same as default)
    """
    mode, prompt = extract_mode_and_prompt(req.prompt)

    if not prompt:
        return CodeResponse(output="(Empty prompt)")

    coder_output = None
    reviewer_output = None
    final_output = None
    judge_result: Dict[str, Any] = {}
    escalated = False
    escalation_reason = ""

    # -------- Mode: coder only --------
    if mode == "code_raw":
        coder_output = run_coder(prompt)
        final_output = coder_output

        # Judge (for logging / dashboard only)
        try:
            judge_result = run_judge(
                original_prompt=prompt,
                coder_output=coder_output or "",
                reviewer_output=final_output or "",
            )
        except Exception as e:
            judge_result = {
                "confidence_score": None,
                "conflict_score": None,
                "judgement_summary": f"Judge failed: {e}",
                "raw_response": "",
                "parse_error": str(e),
            }

    # -------- Mode: review only --------
    elif mode == "review_only":
        try:
            reviewer_output = run_reviewer("", prompt)
            final_output = reviewer_output
        except Exception:
            final_output = prompt

        try:
            judge_result = run_judge(
                original_prompt=prompt,
                coder_output="",
                reviewer_output=final_output or "",
            )
        except Exception as e:
            judge_result = {
                "confidence_score": None,
                "conflict_score": None,
                "judgement_summary": f"Judge failed: {e}",
                "raw_response": "",
                "parse_error": str(e),
            }

    # -------- Mode: with history context --------
    elif mode == "code_reviewed_ctx":
        history_ctx = build_history_context(max_items=5)
        prompt_with_ctx = prompt
        if history_ctx:
            prompt_with_ctx = (
                "Here are some recent interactions between the user and the assistant.\n"
                "Use them as context, but treat the CURRENT REQUEST as primary.\n\n"
                + history_ctx
                + "\n\nCURRENT REQUEST:\n"
                + prompt
            )

        # Step 1: fast coder
        coder_output = run_coder(prompt_with_ctx)

        # Step 2: judge coder-only
        try:
            judge_result = run_judge(
                original_prompt=prompt_with_ctx,
                coder_output=coder_output or "",
                reviewer_output=coder_output or "",
            )
        except Exception as e:
            judge_result = {
                "confidence_score": None,
                "conflict_score": None,
                "judgement_summary": f"Judge failed: {e}",
                "raw_response": "",
                "parse_error": str(e),
            }

        # Step 3: decide escalation
        if ESCALATION_ENABLED:
            do_escalate, reason = should_escalate(judge_result)
        else:
            do_escalate, reason = False, ""

        if ESCALATION_ENABLED and do_escalate:
            escalated = True
            escalation_reason = reason or "auto-escalated to heavy review"
            try:
                reviewer_output = run_reviewer(prompt_with_ctx, coder_output)
                final_output = inject_escalation_comment(
                    reviewer_output or coder_output, escalation_reason
                )
            except Exception:
                final_output = inject_escalation_comment(coder_output, escalation_reason)
        else:
            reviewer_output = None
            final_output = coder_output

    # -------- Default: no tag --------
    else:  # DEFAULT_MODE: code_reviewed
        # Step 1: fast coder
        coder_output = run_coder(prompt)

        # Step 2: judge coder-only
        try:
            judge_result = run_judge(
                original_prompt=prompt,
                coder_output=coder_output or "",
                reviewer_output=coder_output or "",
            )
        except Exception as e:
            judge_result = {
                "confidence_score": None,
                "conflict_score": None,
                "judgement_summary": f"Judge failed: {e}",
                "raw_response": "",
                "parse_error": str(e),
            }

        # Step 3: decide escalation
        if ESCALATION_ENABLED:
            do_escalate, reason = should_escalate(judge_result)
        else:
            do_escalate, reason = False, ""

        if ESCALATION_ENABLED and do_escalate:
            escalated = True
            escalation_reason = reason or "auto-escalated to heavy review"
            try:
                reviewer_output = run_reviewer(prompt, coder_output)
                final_output = inject_escalation_comment(
                    reviewer_output or coder_output, escalation_reason
                )
            except Exception:
                final_output = inject_escalation_comment(coder_output, escalation_reason)
        else:
            reviewer_output = None
            final_output = coder_output

    # ----- Risk tagging for code (logging only) -----
    try:
        risk_info = assess_risk(
            "code",
            {
                "mode": mode,
                "original_prompt": req.prompt,
                "normalized_prompt": prompt,
                "final_output": final_output or "",
            },
        )
    except Exception:
        risk_info = {
            "risk_level": 1,
            "tags": [],
            "reasons": "Risk assessment failed; defaulting to MINOR risk.",
            "kind": "code",
        }

    # ---- History logging ----
    history_logger.log(
        {
            "mode": mode,
            "original_prompt": req.prompt,
            "normalized_prompt": prompt,
            "coder_output": coder_output,
            "reviewer_output": reviewer_output,
            "final_output": final_output,
            "escalated": escalated,
            "escalation_reason": escalation_reason,
            "judge": {
                "confidence_score": judge_result.get("confidence_score") if judge_result else None,
                "conflict_score": judge_result.get("conflict_score") if judge_result else None,
                "judgement_summary": judge_result.get("judgement_summary") if judge_result else None,
                "raw_response": judge_result.get("raw_response") if judge_result else None,
                "parse_error": judge_result.get("parse_error") if judge_result else None,
            },
            "risk": risk_info,
            # New: model-used telemetry
            "models": {
                "coder": CODER_MODEL_NAME,
                "reviewer": REVIEWER_MODEL_NAME,
                "judge": JUDGE_MODEL_NAME if JUDGE_ENABLED else None,
            },
        }
    )

    return CodeResponse(output=final_output or "")


# =========================
# /api/study endpoint
# =========================

@app.post("/api/study", response_model=StudyResponse)
def study(req: StudyRequest):
    """
    Study / teaching endpoint.

    Tags (first line):
      ///short  -> short explanation
      ///deep   -> deep dive
      ///quiz   -> quiz mode
      (no tag) -> normal explanation
    """
    style, prompt = extract_study_style_and_prompt(req.prompt)

    if not prompt:
        return StudyResponse(output="(Empty study prompt)")

    study_output = run_study(prompt, style=style)

    # Log as a separate mode for dashboard
    history_logger.log(
        {
            "mode": f"study_{style}",
            "original_prompt": req.prompt,
            "normalized_prompt": prompt,
            "coder_output": None,
            "reviewer_output": None,
            "final_output": study_output,
            "escalated": False,
            "escalation_reason": "",
            "judge": None,
            # New: model-used telemetry
            "models": {
                "study": STUDY_MODEL_NAME,
            },
        }
    )

    return StudyResponse(output=study_output)


# =========================
# /api/vision endpoint (generic, not chat-specific)
# =========================

@app.post("/api/vision", response_model=VisionResponse)
async def vision_endpoint(
    file: UploadFile = File(...),
    prompt: str = Form(""),
    mode: str = Form("auto"),
):
    """
    Vision / image endpoint.

    Usage:
      - Upload an image (screenshot, UI, code, error, photo).
      - Optional text prompt.
      - Optional mode:
          "auto" (default)
          "describe"
          "ocr"
          "code"
          "debug"
    """
    if not VISION_ENABLED:
        return VisionResponse(output="Vision is disabled in config (VISION_ENABLED = False).")

    image_bytes = await file.read()
    if not image_bytes:
        return VisionResponse(output="(No image data received.)")

    vision_output = run_vision(
        image_bytes=image_bytes,
        user_prompt=prompt or "",
        mode=mode or "auto",
    )

    # Log to history for dashboard
    history_logger.log(
        {
            "mode": f"vision_{mode or 'auto'}",
            "original_prompt": prompt,
            "normalized_prompt": prompt,
            "coder_output": None,
            "reviewer_output": None,
            "final_output": vision_output,
            "escalated": False,
            "escalation_reason": "",
            "judge": None,
            # New: model-used telemetry
            "models": {
                "vision": VISION_MODEL_NAME,
            },
        }
    )

    return VisionResponse(output=vision_output)


# =========================
# /api/tools/execute endpoint
# =========================

@app.post("/api/tools/execute", response_model=ToolExecResponse)
def tools_execute(req: ToolExecRequest):
    """
    Manual tools runtime execution endpoint.

    This is primarily for development / debugging and is intentionally
    simple. It delegates to tools_runtime.execute_tool, which handles
    feature flags, registry lookup, and error handling.

    Request body:
        {
          "tool": "ping",
          "args": { "message": "hello" }
        }
    """
    context = {
        "source": "api.tools.execute",
    }
    record = execute_tool(req.tool, req.args or {}, context)

    return ToolExecResponse(
        ok=bool(record.get("ok")),
        tool=record.get("tool") or req.tool,
        result=record.get("result"),
        error=record.get("error"),
        risk=record.get("risk"),
    )


# =====================================================
# 🔐 NEW — /api/security/auth  (V3.5 security system)
# =====================================================

@app.post("/api/security/auth")
async def api_security_auth(
    payload: Dict[str, Any] = Body(...),
):
    """
    Create a temporary authorization session for security-sensitive actions.

    This does NOT enforce or block anything by itself — it only records
    an approval, which can later be consumed by enforcement code
    (e.g., around tool execution).

    Example payload:
    {
      "profile_id": "A",
      "scope": "tool:delete_file",
      "auth_level": 4,
      "ttl_seconds": 300,
      "max_uses": 1,
      "secret": "optional-password-or-phrase"
    }
    """
    profile_id = payload.get("profile_id") or ""
    scope = payload.get("scope") or ""
    auth_level = payload.get("auth_level")

    if not profile_id or not scope:
        raise HTTPException(status_code=400, detail="profile_id and scope are required.")
    if auth_level is None:
        raise HTTPException(status_code=400, detail="auth_level is required.")

    try:
        ttl_seconds = int(payload.get("ttl_seconds", 300))
        max_uses = int(payload.get("max_uses", 1))
        secret = payload.get("secret")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ttl_seconds or max_uses.")

    try:
        session = create_security_session(
            profile_id=profile_id,
            scope=scope,
            auth_level=int(auth_level),
            ttl_seconds=ttl_seconds,
            max_uses=max_uses,
            secret=secret,
        )
        return {"ok": True, "session": session}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# =========================
# /dashboard endpoint
# =========================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(limit: int = 50):
    """
    Dashboard UI for traces (code, study, chat, vision).
    """
    return render_dashboard(limit=limit)


# =========================
# /chat UI endpoint (static HTML file)
# =========================

@app.get("/chat", response_class=HTMLResponse)
def chat_page():
    """
    Serve the static multi-profile chat UI (project_root/static/chat.html).
    """
    # backend/code_server.py -> project root -> static/chat.html
    project_root = Path(__file__).resolve().parent.parent
    html_path = project_root / "static" / "chat.html"
    if not html_path.exists():
        return HTMLResponse("<h2>chat.html not found</h2>", status_code=500)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def root():
    """
    Root → redirect to chat UI.
    """
    return chat_page()
