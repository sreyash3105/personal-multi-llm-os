# backend/modules/automation/executor.py
"""
Automation executor + planner.
UPDATED: Now logs a complete 'Trace' of the event:
Planner -> Worker (Results) -> Security -> Risk Assessment.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

# --- Imports ---
try:
    from backend.modules.code.pipeline import call_ollama
except Exception:
    call_ollama = None

try:
    from backend.modules.tools.tools_runtime import execute_tool
except Exception:
    execute_tool = None

try:
    from backend.modules.vision.screen_locator import locate_action_plan
except Exception:
    locate_action_plan = None

try:
    from backend.modules.telemetry.history import history_logger
except Exception:
    history_logger = None

try:
    from backend.modules.security.security_engine import SecurityEngine
except Exception:
    SecurityEngine = None

try:
    from backend.modules.automation.step_sanitizer import sanitize_steps, SanitizationError
except Exception:
    sanitize_steps = None
    SanitizationError = Exception

# NEW: Import Risk Assessment
try:
    from backend.modules.telemetry.risk import assess_risk
except Exception:
    def assess_risk(*args, **kwargs): return {"risk_level": 1.0, "reason": "Risk module missing"}

try:
    from backend.modules.common.io_guards import extract_json_object
except Exception:
    extract_json_object = None

logger = logging.getLogger(__name__)

# --- Planner Prompt ---
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

Return ONLY a single valid JSON object.
"""

DEFAULT_PLANNER_MODEL = "llama3.1:8b"


def _parse_json_from_text(raw: str) -> Dict[str, Any]:
    if not raw or not extract_json_object:
        return {}
    data = extract_json_object(raw)
    if isinstance(data, dict):
        return data
    elif isinstance(data, list):
        return {"steps": data}
    return {}


def plan(user_text: str, context: Optional[Dict[str, Any]] = None, model_name: Optional[str] = None) -> Dict[str, Any]:
    context = context or {}
    model = model_name or DEFAULT_PLANNER_MODEL

    if call_ollama is None:
        return {"title": "Planner Unavailable", "confidence": 0.0, "steps": [], "notes": "No LLM connection"}

    prompt = PLANNER_SYSTEM_PROMPT + "\n\nInstruction:\n" + (user_text or "") + "\n\nRespond with JSON only."
    try:
        raw = call_ollama(prompt, model)
    except Exception as e:
        logger.exception("Planner error")
        return {"title": "Error", "confidence": 0.0, "steps": [], "notes": str(e)}

    parsed = _parse_json_from_text(raw)
    steps = parsed.get("steps") if isinstance(parsed.get("steps"), list) else []
    return {
        "title": parsed.get("title", "Untitled Plan"),
        "confidence": float(parsed.get("confidence", 0.0)),
        "steps": steps,
        "notes": parsed.get("notes", ""),
        "raw": parsed
    }


def _execute_steps(steps: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if execute_tool is None:
        raise RuntimeError("Tools runtime missing")

    results = []
    for step in steps:
        sid = step.get("id") or str(time.time())
        tool_name = step.get("tool") or step.get("action")
        args = step.get("args") or {}
        
        try:
            # Try calling tool with context first, then without
            try:
                res = execute_tool(tool_name, args, context=context)
            except TypeError:
                res = execute_tool(tool_name, args)
                
            # Normalize result
            if isinstance(res, dict) and "ok" in res:
                results.append({"id": sid, "ok": res["ok"], "result": res.get("result"), "error": res.get("error")})
            else:
                results.append({"id": sid, "ok": True, "result": res, "error": None})
        except Exception as e:
            results.append({"id": sid, "ok": False, "result": None, "error": str(e)})
            
    return results


def _simulate_steps(steps: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{"id": s.get("id"), "ok": True, "result": "SIMULATED", "step": s} for s in steps]


def plan_and_execute(user_text: str, context: Optional[Dict[str, Any]] = None, execute: bool = False) -> Dict[str, Any]:
    """
    The Master Loop: Plan -> Security -> Execute -> Assess Risk -> Log
    """
    context = context or {}
    
    # 1. PLANNER
    plan_obj = plan(user_text, context=context)
    
    # Vision context check (optional)
    if locate_action_plan and ("click" in user_text.lower() or "type" in user_text.lower()):
        screen_plan = locate_action_plan(user_text, context.get("profile_id"))
        if screen_plan and screen_plan.get("ok"):
            # Re-plan with vision data
            user_text_v = f"Context: Screen Locator found: {screen_plan}. User: {user_text}"
            plan_obj = plan(user_text_v, context=context)

    steps = plan_obj.get("steps", [])

    # 2. SANITIZER
    if sanitize_steps:
        try:
            steps = sanitize_steps(steps)
        except SanitizationError as e:
            return {"ok": False, "error": f"Sanitizer blocked: {e}"}

    # 3. SECURITY ENGINE (The Gatekeeper)
    security_eval = None
    if SecurityEngine:
        try:
            security_eval = SecurityEngine.shared().evaluate({
                "text": user_text,
                "intent": "automation",
                "plan": plan_obj
            })
            if security_eval.get("action") == "block":
                return {"ok": False, "error": "Security Blocked", "security": security_eval}
        except Exception:
            pass

    # 4. WORKER (Execution)
    executed = False
    results = []
    error = None
    
    try:
        if execute:
            if security_eval and security_eval.get("action") == "require_approval":
                error = "Approval Required"
            else:
                results = _execute_steps(steps, context)
                executed = True
        else:
            results = _simulate_steps(steps, context)
    except Exception as e:
        error = str(e)

    # 5. RISK ASSESSMENT (Post-Mortem)
    # We analyze what we actually did (or planned to do)
    final_risk = assess_risk("automation", {"plan": steps, "results": results})

    # 6. HISTORY LOGGING (The Full Trace)
    if history_logger:
        log_payload = {
            "mode": "automation",
            "original_prompt": user_text,
            "final_output": "Executed" if executed else "Simulated",
            # The structured brain data:
            "trace": {
                "planner": plan_obj,
                "worker": results,
                "security": security_eval,
                "risk_assessment": final_risk
            }
        }
        history_logger.log(log_payload)

    return {
        "ok": not error,
        "error": error,
        "plan": plan_obj,
        "results": results,
        "executed": executed,
        "risk": final_risk
    }