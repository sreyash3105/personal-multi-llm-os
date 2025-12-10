# backend/modules/automation/router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# guarded import of executor
try:
    from backend.modules.automation.executor import plan, plan_and_execute
except Exception:
    try:
        from backend.automation.executor import plan, plan_and_execute
    except Exception:
        plan = None
        plan_and_execute = None

router = APIRouter()

class AutomationRequest(BaseModel):
    text: str
    profile_id: Optional[str] = None
    chat_id: Optional[str] = None
    execute: bool = False
    require_approval: bool = False

@router.post("/api/automation/run")
def api_automation_run(body: AutomationRequest):
    if plan_and_execute is None and plan is None:
        raise HTTPException(status_code=500, detail="Automation executor not available on server")
    ctx = {"profile_id": body.profile_id, "chat_id": body.chat_id}
    if not body.execute:
        if plan_and_execute is not None:
            return plan_and_execute(body.text, context=ctx, execute=False)
        return {"ok": True, "plan": plan(body.text, context=ctx), "executed": False}
    if plan_and_execute is None:
        raise HTTPException(status_code=500, detail="Execution not supported (plan_and_execute missing)")
    return plan_and_execute(body.text, context=ctx, execute=True, require_approval=body.require_approval)
