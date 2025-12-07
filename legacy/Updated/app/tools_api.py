"""
FastAPI router exposing the local tools runtime over HTTP.

Routes:
  GET  /api/tools       → list registered tools (name, description, input_schema)
  POST /api/tools/run   → run a tool with params

This layer has **no dependency on LLMs or chat pipeline**.
It just exposes the Python tools you register in tools_runtime.
"""

from __future__ import annotations
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.tools_runtime import list_tools, run_tool

router = APIRouter()


# --------------------------------------------------------
# Request model for POST /api/tools/run
# --------------------------------------------------------
class ToolRunRequest(BaseModel):
    tool: str
    params: Dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------
# Routes
# --------------------------------------------------------
@router.get("/api/tools")
def api_list_tools():
    """Return metadata for all registered tools."""
    return {"tools": list_tools()}


@router.post("/api/tools/run")
def api_run_tool(req: ToolRunRequest):
    """
    Execute a tool by name.

    Body:
      {
        "tool": "ping",
        "params": { "message": "hello from laptop" }
      }
    """
    result = run_tool(req.tool, req.params)
    return {"tool": req.tool, **result}
