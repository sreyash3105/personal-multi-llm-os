# backend/modules/automation/executor.py
"""
Automation executor + planner (full implementation).

Drop-in module for:
- plan(user_text, context) -> returns planner JSON (title, confidence, steps, notes)
- plan_and_execute(user_text, context, execute=False, require_approval=False)
    -> runs sanitizer, security checks, optionally executes steps (or simulates)
- _execute_steps(...) executes steps using your tools runtime (execute_tool)
- _simulate_steps(...) returns simulated results (safe default)

This file expects the following functions/modules to exist in your repo:
- backend.modules.code.pipeline.call_ollama(prompt, model_name)  (LLM caller)
- backend.modules.tools.tools_runtime.execute_tool(tool_name, args, context)  (tools executor)
- backend.modules.telemetry.history.history_logger (history_logger.log(dict))
- backend.modules.automation.step_sanitizer.sanitize_steps(...) (sanitizer)
- backend.modules.security_engine.SecurityEngine (optional)

If any of those are missing, the module will degrade gracefully and return informative errors.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

# LLM planner (uses your repo LLM runner)
try:
    from backend.modules.code.pipeline import call_ollama
except Exception:
    try:
        from backend.code.pipeline import call_ollama
    except Exception:
        call_ollama = None

# tools runtime execute function
try:
    from backend.modules.tools.tools_runtime import execute_tool
except Exception:
    try:
        from backend.tools.tools_runtime import execute_tool
    except Exception:
        execute_tool = None

# history logger for telemetry/audit
try:
    from backend.modules.telemetry.history import history_logger
except Exception:
    try:
        from backend.telemetry.history import history_logger
    except Exception:
        history_logger = None

# security engine (optional)
try:
    from backend.modules.security_engine import SecurityEngine
except Exception:
    try:
        from backend.security_engine import SecurityEngine
    except Exception:
        SecurityEngine = None

# step sanitizer (conservative safety gate)
try:
    from backend.modules.automation.step_sanitizer import sanitize_steps, SanitizationError
except Exception:
    try:
        from backend.automation.step_sanitizer import sanitize_steps, SanitizationError
    except Exception:
        sanitize_steps = None
        SanitizationError = Exception  # fallback


logger = logging.getLogger(__name__)


# Planner prompt (adjust or externalize as needed)
PLANNER_SYSTEM_PROMPT = """
You are an automation planner for a local PC automation system.
Given a user instruction, output an ordered JSON object with:
 - "title": short title of the plan
 - "confidence": a float between 0.0 and 1.0
 - "steps": a JSON array of step objects in execution order
 - "notes": optional natural language notes

Each step object should look like:
{
  "id": "s1",
  "action": "tool" | "file" | "shell" | "click" | "keyboard" | "note",
  "tool": "optional-tool-name",
  "args": { ... },
  "description": "human friendly description"
}

Return ONLY a single valid JSON object. If you cannot produce a safe plan, return:
{ "title": "", "confidence": 0.0, "steps": [], "notes": "reason..." }
"""

DEFAULT_PLANNER_MODEL = "small"


def _parse_json_from_text(raw: str) -> Dict[str, Any]:
    """
    Try to extract the first JSON object in raw text and parse it.
    Returns a dict (empty dict on failure).
    """
    if not raw:
        return {}
    txt = str(raw).strip()
    if "{" in txt and "}" in txt:
        try:
            candidate = txt[txt.find("{") : txt.rfind("}") + 1]
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
            # sometimes planner returns a top-level list or other - wrap
            return {"steps": data} if isinstance(data, list) else {}
        except Exception as e:
            logger.debug("Planner JSON parse failed: %s; raw (truncated): %s", e, txt[:1000])
            return {}
    # fallback: try plain json
    try:
        data = json.loads(txt)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def plan(user_text: str, context: Optional[Dict[str, Any]] = None, model_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate a JSON plan from the LLM planner.
    Returns a dict with keys: title, confidence, steps (list), notes, raw
    """
    context = context or {}
    model = model_name or DEFAULT_PLANNER_MODEL

    if call_ollama is None:
        logger.warning("call_ollama not available; planner cannot run.")
        return {"title": "", "confidence": 0.0, "steps": [], "notes": "planner unavailable", "raw": None}

    prompt = PLANNER_SYSTEM_PROMPT + "\n\nInstruction:\n" + (user_text or "") + "\n\nRespond with JSON only."
    try:
        raw = call_ollama(prompt, model)
    except Exception as e:
        logger.exception("Planner call failed: %s", e)
        return {"title": "", "confidence": 0.0, "steps": [], "notes": f"planner error: {e}", "raw": None}

    parsed = _parse_json_from_text(raw)
    title = parsed.get("title", "") if isinstance(parsed, dict) else ""
    confidence = float(parsed.get("confidence", 0.0) or 0.0) if isinstance(parsed, dict) else 0.0
    steps = parsed.get("steps") if isinstance(parsed, dict) else []
    notes = parsed.get("notes") if isinstance(parsed, dict) else ""
    # Ensure steps is a list
    if not isinstance(steps, list):
        steps = []

    return {"title": title, "confidence": confidence, "steps": steps, "notes": notes, "raw": parsed}


def _execute_steps(steps: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Execute each step using execute_tool (if available).
    Returns list of result dicts per step: {id, ok, result, error, raw}
    """
    if execute_tool is None:
        raise RuntimeError("tools runtime (execute_tool) not available")

    results: List[Dict[str, Any]] = []
    for step in steps:
        sid = step.get("id") or str(time.time())
        action = (step.get("action") or "").lower()
        tool_name = step.get("tool") or action
        args = step.get("args") or {}
        try:
            # dispatch to execute_tool - many tools accept (tool_name, args, context)
            try:
                res = execute_tool(tool_name, args, context=context)
            except TypeError:
                # fallback signatures
                try:
                    res = execute_tool(tool_name, args)
                except TypeError:
                    res = execute_tool(step)  # last-resort attempt
            # normalize result
            if not isinstance(res, dict):
                results.append({"id": sid, "ok": True, "result": res, "error": None, "raw": res})
            else:
                results.append({"id": sid, "ok": bool(res.get("ok")) if "ok" in res else True, "result": res.get("result") if isinstance(res, dict) else res, "error": res.get("error") if isinstance(res, dict) else None, "raw": res})
        except Exception as e:
            logger.exception("Step execution failed (id=%s): %s", sid, e)
            results.append({"id": sid, "ok": False, "result": None, "error": str(e), "raw": None})
    return results


def _simulate_steps(steps: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Simulate each step (dry-run). Return a simulated result object for each step.
    """
    results: List[Dict[str, Any]] = []
    for step in steps:
        sid = step.get("id") or str(time.time())
        results.append(
            {
                "id": sid,
                "ok": True,
                "result": {"simulated": True, "action": step.get("action"), "tool": step.get("tool"), "args": step.get("args")},
                "error": None,
                "raw": None,
            }
        )
    return results


def _run_security_eval(user_text: str, context: Dict[str, Any], plan_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Call SecurityEngine.shared().evaluate(...) if available.
    Returns evaluation dict or None.
    """
    if SecurityEngine is None:
        return None
    try:
        sec = SecurityEngine.shared()
        return sec.evaluate({"text": user_text, "intent": "automation", "profile_id": context.get("profile_id"), "risk_score": 0.0, "plan": plan_obj})
    except Exception as e:
        logger.exception("SecurityEngine evaluation failed: %s", e)
        return {"error": str(e)}


def plan_and_execute(user_text: str, context: Optional[Dict[str, Any]] = None, execute: bool = False, require_approval: bool = False) -> Dict[str, Any]:
    """
    Create plan, sanitize, security-evaluate, and optionally execute.

    Returns:
      {
        "ok": bool,
        "plan": {...},
        "executed": bool,
        "results": [ ... ],
        "security": {...} | None,
        "error": "..." | None
      }
    """
    context = context or {}
    plan_obj = plan(user_text, context=context)
    steps = plan_obj.get("steps") or []

    # Basic validation
    if not steps:
        return {"ok": False, "error": "No actionable steps from planner", "plan": plan_obj, "executed": False, "results": [], "security": None}

    # Run sanitizer (if available)
    if sanitize_steps is not None:
        try:
            clean_steps = sanitize_steps(steps)
        except SanitizationError as e:
            logger.warning("Plan rejected by sanitizer: %s", e)
            return {"ok": False, "error": f"Plan rejected by sanitizer: {e}", "plan": plan_obj, "executed": False, "results": [], "security": None}
    else:
        # if sanitizer not present, use original steps but log a warning
        logger.warning("Step sanitizer not available; proceeding without sanitization.")
        clean_steps = steps

    # Simple textual risk heuristic (conservative)
    tl = (user_text or "").lower()
    risk = 0.0
    if any(k in tl for k in ("delete ", "rm -rf", "format ", "factory reset", "shutdown", "reboot")):
        risk = max(risk, 8.0)

    # Security evaluation
    security_eval = _run_security_eval(user_text, context, plan_obj)
    if security_eval:
        action = security_eval.get("action")
        # If security blocks -> return early
        if action == "block":
            return {"ok": False, "error": "Blocked by SecurityEngine", "plan": plan_obj, "executed": False, "results": [], "security": security_eval}
        # If require approval and caller requested require_approval True, honor that
        if require_approval and action == "require_approval":
            return {"ok": False, "error": "Requires approval", "plan": plan_obj, "executed": False, "results": [], "security": security_eval}

    # Execute or simulate
    executed = False
    results: List[Dict[str, Any]] = []
    try:
        if execute:
            if execute_tool is None:
                return {"ok": False, "error": "Tools runtime unavailable for execution", "plan": plan_obj, "executed": False, "results": [], "security": security_eval}
            # Double-check security: if security requires approval, do not execute
            if security_eval and security_eval.get("action") == "require_approval":
                return {"ok": False, "error": "Requires approval (security)", "plan": plan_obj, "executed": False, "results": [], "security": security_eval}
            results = _execute_steps(clean_steps, context)
            executed = True
        else:
            results = _simulate_steps(clean_steps, context)
            executed = False
    except Exception as e:
        logger.exception("Execution error: %s", e)
        return {"ok": False, "error": str(e), "plan": plan_obj, "executed": executed, "results": results, "security": security_eval}

    # Audit log to history (best-effort)
    try:
        if history_logger is not None:
            history_logger.log(
                {
                    "mode": "automation",
                    "original_prompt": user_text,
                    "normalized_prompt": user_text,
                    "final_output": results,
                    "escalated": False,
                    "escalation_reason": "",
                    "judge": None,
                    "chat_profile_id": context.get("profile_id"),
                    "chat_profile_name": context.get("profile_name"),
                    "chat_id": context.get("chat_id"),
                    "chat_model_used": None,
                    "chat_smart_plan": plan_obj.get("title"),
                    "models": {"planner": DEFAULT_PLANNER_MODEL},
                    "plan": plan_obj,
                    "results": results,
                }
            )
    except Exception:
        logger.exception("Failed to write automation history log (non-fatal).")

    return {"ok": True, "plan": plan_obj, "executed": executed, "results": results, "security": security_eval, "error": None}
