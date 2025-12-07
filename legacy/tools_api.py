# tools_api.py
"""
FastAPI router exposing the tools runtime over HTTP.

Endpoints:

  GET  /api/tools
    -> list all registered tools (name, description, input_schema)

  POST /api/tools/run
    Body: { "tool": "<name>", "params": { ... } }
    -> executes the tool and returns its result wrapper:
       {
         "tool": "<name>",
         "ok": true/false,
         "result": {...}   # when ok == true
         "error": "...",   # when ok == false
         "detail": "..."   # optional
       }

This does NOT integrate with LLMs yet; it's just a clean tools surface
for your laptop, Postman, scripts, and future orchestrations.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from tools_runtime import list_tools, run_tool

router = APIRouter()


# =========================
# Pydantic models
# =========================

class ToolRunRequest(BaseModel):
    tool: str
    params: Dict[str, Any] = Field(default_factory=dict)


# =========================
# Routes
# =========================

@router.get("/api/tools")
def api_list_tools():
    """
    Return all registered tools and their metadata.
    """
    return {
        "tools": list_tools(),
    }


@router.post("/api/tools/run")
def api_run_tool(req: ToolRunRequest):
    """
    Execute a tool by name.

    Body:
      {
        "tool": "ping",
        "params": {
          "message": "hello from laptop"
        }
      }
    """
    result = run_tool(req.tool, req.params)
    # result already has ok/result/error/detail fields
    return {
        "tool": req.tool,
        **result,
    }
