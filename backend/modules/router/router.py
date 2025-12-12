# backend/modules/router/router.py
"""
Robust router for intent classification & routing.

- Uses hybrid classification (rules + llm)
- Routes to available subsystems (tools runtime, code pipeline, automation executor, chat pipeline)
- Guards imports so server won't crash when modules are missing
- Default behavior is safe: dry-run/simulate rather than execute unless explicit execute=True
"""

import logging
import importlib
from typing import Dict, Any, List, Optional

from backend.modules.router.classifier import llm_intent_score, merge_scores
from backend.modules.router.rules import rule_based_intent

logger = logging.getLogger(__name__)

# -------------------------
# Guarded multi-variant imports
# -------------------------

# Tools runtime: prefer execute_tool or execute_tool_record or execute_text variants
_tools_runner = None
_tools_found: List[str] = []
_tools_candidates = [
    "backend.modules.tools.tools_runtime",
    "backend.modules.tools_runtime",
    "backend.tools.tools_runtime",
    "backend.tools_runtime",
]
_tools_fns = [
    "execute_tool",
    "execute_tool_record",
    "run_text_tool",
    "run_tool",
    "run_text",
    "execute_text_tool",
]

for modname in _tools_candidates:
    try:
        mod = importlib.import_module(modname)
    except Exception:
        continue
    for fn in _tools_fns:
        fnobj = getattr(mod, fn, None)
        if callable(fnobj):
            _tools_runner = fnobj
            _tools_found.append(f"{modname}.{fn}")
            break
    if _tools_runner:
        break

# Code pipeline: try call_ollama, call_code, run_code, run_code_request
_code_runner = None
_code_found: List[str] = []
_code_candidates = [
    "backend.modules.code.pipeline",
    "backend.code.pipeline",
    "backend.modules.code",
    "backend.code",
]
_code_fns = ["run_code_request", "run_code", "call_code", "call_ollama", "execute_code"]

for modname in _code_candidates:
    try:
        mod = importlib.import_module(modname)
    except Exception:
        continue
    for fn in _code_fns:
        fnobj = getattr(mod, fn, None)
        if callable(fnobj):
            _code_runner = fnobj
            _code_found.append(f"{modname}.{fn}")
            break
    if _code_runner:
        break

# Chat pipeline: prefer run_chat_smart, run_chat_simple, run_chat, handle_message
_chat_handler = None
_chat_found: List[str] = []
_chat_candidates = [
    "backend.modules.chat.chat_pipeline",
    "backend.chat.chat_pipeline",
    "backend.modules.chat_pipeline",
]
_chat_fns = ["run_chat_smart", "run_chat_simple", "run_chat", "handle_message", "handle_chat"]

for modname in _chat_candidates:
    try:
        mod = importlib.import_module(modname)
    except Exception:
        continue
    for fn in _chat_fns:
        fnobj = getattr(mod, fn, None)
        if callable(fnobj):
            _chat_handler = fnobj
            _chat_found.append(f"{modname}.{fn}")
            break
    if _chat_handler:
        break

# Automation executor: plan and plan_and_execute
_automation_plan = None
_automation_execute = None
_auto_found: List[str] = []
_auto_candidates = [
    "backend.modules.automation.executor",
    "backend.automation.executor",
    "backend.modules.automation",
    "backend.automation",
]
_auto_plan_fns = ["plan", "build_plan"]
_auto_exec_fns = ["plan_and_execute", "execute_plan", "run_plan"]

for modname in _auto_candidates:
    try:
        mod = importlib.import_module(modname)
    except Exception:
        continue
    for fn in _auto_plan_fns:
        fnobj = getattr(mod, fn, None)
        if callable(fnobj):
            _automation_plan = fnobj
            _auto_found.append(f"{modname}.{fn}")
            break
    for fn in _auto_exec_fns:
        fnobj = getattr(mod, fn, None)
        if callable(fnobj):
            _automation_execute = fnobj
            _auto_found.append(f"{modname}.{fn}")
            break
    if _automation_plan or _automation_execute:
        break

# Security engine
SecurityEngine = None
try:
    mod = importlib.import_module("backend.modules.security.security_engine")
    SecurityEngine = getattr(mod, "SecurityEngine", None)
except Exception:
    try:
        mod = importlib.import_module("backend.security_engine")
        SecurityEngine = getattr(mod, "SecurityEngine", None)
    except Exception:
        SecurityEngine = None

logger.debug(
    "Router bound implementations: tools=%s code=%s chat=%s automation=%s security=%s",
    _tools_found,
    _code_found,
    _chat_found,
    _auto_found,
    bool(SecurityEngine),
)

# -------------------------
# Router config
# -------------------------

DEFAULT_ROUTER_CONFIG = {
    "risk_threshold_auto_approve": 2.5,  # below this, router can auto run mild ops
    "risk_threshold_require_approval": 3.0,
}


# -------------------------
# Classification
# -------------------------

def classify_intent(text: str) -> Dict[str, Any]:
    """
    Hybrid classification: rule-based first, LLM optional, then merge.
    Returns {"intent": str, "confidence": float, "evidence": {...}}
    """
    text = text or ""
    rule = rule_based_intent(text)
    llm = llm_intent_score(text)
    merged = merge_scores(rule, llm)
    logger.info(
        "Router classify: intent=%s conf=%s (rule=%s llm=%s)",
        merged.get("intent"),
        merged.get("confidence"),
        rule.get("score"),
        (llm.get("score") if llm else None),
    )
    return merged


# -------------------------
# Utility helpers
# -------------------------

def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except TypeError:
        # try to call with fewer args if signature differs
        try:
            return fn(*args)
        except Exception as e:
            logger.exception("Safe call failed: %s", e)
            raise
    except Exception as e:
        logger.exception("Safe call failed: %s", e)
        raise


# -------------------------
# Main route_request
# -------------------------


def route_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload expected keys:
      - text (str)
      - profile_id, chat_id, source (optional)
      - execute: bool (optional) => whether to execute or just plan
    Returns a structured response with routing decision and any action result.
    """
    text = payload.get("text", "") or ""
    profile_id = payload.get("profile_id")
    chat_id = payload.get("chat_id")
    source = payload.get("source", "chat")
    execute = bool(payload.get("execute", False))

    decision = classify_intent(text)
    intent = decision.get("intent", "unknown")
    confidence = float(decision.get("confidence", 0.0) or 0.0)

    response: Dict[str, Any] = {
        "ok": True,
        "intent": intent,
        "confidence": confidence,
        "raw_decision": decision,
        "action": None,
        "result": None,
    }

    # simple risk heuristic
    risk_score = 0.0
    tl = (text or "").lower()
    if intent in ("unsafe",):
        risk_score = 8.0
    if any(k in tl for k in ("delete ", "rm -rf", "format ", "factory reset", "shutdown", "reboot")):
        risk_score = max(risk_score, 7.0)
    response["risk_score"] = risk_score

    # Security evaluation (if available)
    if SecurityEngine is not None and intent in ("automation", "file_op", "unsafe", "tool"):
        try:
            sec = SecurityEngine.shared()
            # NOTE: We use a simplified payload here as the full context 
            # (plan_obj) is not generated yet.
            sec_decision = sec.evaluate(
                risk_score=risk_score,
                operation_type=intent,
                context_tags={"source": source, "profile_id": profile_id},
            )
            response["security"] = sec_decision
            # NOTE: sec_decision doesn't have an "action" key here, 
            # security enforcement is typically handled later.
        except Exception as e:
            logger.exception("SecurityEngine.evaluate failed: %s", e)
            response.setdefault("security", {"error": str(e)})

    # Routing
    try:
        # TOOL intent -> tools runtime
        if intent == "tool" and _tools_runner is not None:
            response["action"] = "tool_call"
            if execute:
                # forward to tools runner
                try:
                    res = _safe_call(_tools_runner, text, {"profile_id": profile_id, "chat_id": chat_id})
                except Exception:
                    # some runtimes expect (tool_name, args, context)
                    try:
                        res = _safe_call(_tools_runner, text, {}, {"profile_id": profile_id, "chat_id": chat_id})
                    except Exception as e:
                        res = {"ok": False, "error": str(e)}
                response["result"] = res
            else:
                response["result"] = {"message": "Tool call planned", "text": text}
            return response

        # FILE operations -> route to tools runtime
        if intent == "file_op" and _tools_runner is not None:
            response["action"] = "file_op"
            if execute:
                try:
                    res = _safe_call(_tools_runner, text, {"profile_id": profile_id, "chat_id": chat_id})
                except Exception:
                    try:
                        res = _safe_call(_tools_runner, text, {}, {"profile_id": profile_id, "chat_id": chat_id})
                    except Exception as e:
                        res = {"ok": False, "error": str(e)}
                response["result"] = res
            else:
                response["result"] = {"message": "File op classified; run with execute=true"}
            return response

        # CODE intent -> code pipeline
        if intent == "code" and _code_runner is not None:
            response["action"] = "code_pipeline"
            if execute:
                try:
                    res = _safe_call(_code_runner, text, profile_id, chat_id)
                except Exception:
                    try:
                        res = _safe_call(_code_runner, text)
                    except Exception as e:
                        res = {"ok": False, "error": str(e)}
                response["result"] = res
            else:
                response["result"] = {"message": "Code request classified; run with execute=true"}
            return response

        # AUTOMATION intent -> automation planner/executor
        if intent == "automation" and (_automation_execute is not None or _automation_plan is not None):
            response["action"] = "automation"
            ctx = {"profile_id": profile_id, "chat_id": chat_id}
            if execute and _automation_execute is not None:
                try:
                    res = _safe_call(_automation_execute, text, context=ctx, execute=True)
                except TypeError:
                    # fallback signature differences
                    try:
                        res = _safe_call(_automation_execute, text, ctx, True)
                    except Exception as e:
                        res = {"ok": False, "error": str(e)}
                response["result"] = res
            elif _automation_plan is not None:
                try:
                    pl = _safe_call(_automation_plan, text, context=ctx)
                except TypeError:
                    try:
                        pl = _safe_call(_automation_plan, text)
                    except Exception as e:
                        pl = {"title": "", "confidence": 0.0, "steps": [], "notes": str(e)}
                # simulate results for dry-run
                response["result"] = {"plan": pl, "simulated": True}
            else:
                response["result"] = {"message": "Automation classified but executor unavailable"}
            return response

        # 🟢 FINAL FALLBACK: All other intents (chat, unknown, etc.) simply return the decision.
        # This prevents the router from crashing by trying to execute the complex chat handler.
        response["action"] = "chat"
        response["result"] = {"message": "Chat request classified. Execution is delegated to the chat pipeline handler."}
        return response

    except Exception as e:
        logger.exception("Routing execution failed: %s", e)
        response["ok"] = False
        response["result"] = {"error": str(e)}
        return response