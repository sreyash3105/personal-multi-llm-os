"""
risk.py

Lightweight, heuristic risk tagging for the Personal Local AI OS.

Goal (V3.4.x):
- Provide a simple, best-effort risk assessment for:
    - tool executions
    - (later) code generations, system calls, etc.
- Attach results to history records and tool execution logs.

IMPORTANT:
- This module MUST NOT raise.
- It MUST NOT block execution.
- It is purely additive metadata for observability and future V3.5 security work.

Risk levels (aligned with your design, but used here ONLY for tagging/logging):

1 — MINOR          -> effectively safe, normal operations
2 — LOW            -> slightly sensitive, but usually fine
3 — MEDIUM         -> potentially impactful (filesystem writes, deletes, etc.)
4 — MINUTE RISK    -> more dangerous patterns (shell, subprocess, network)
5 — RISKY          -> highly sensitive / destructive patterns
6 — TOO MUCH RISKY -> reserved for future strict policies

For now, this module will mostly emit 1–4.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _normalize_text(payload: Any) -> str:
    """
    Turn mixed payload (dict / list / str / other) into a single
    lowercase text blob for heuristic scanning.
    """
    try:
        if isinstance(payload, str):
            return payload.lower()
        if isinstance(payload, dict):
            parts: List[str] = []
            for k, v in payload.items():
                parts.append(str(k))
                parts.append(str(v))
            return " ".join(parts).lower()
        if isinstance(payload, (list, tuple)):
            parts = [str(x) for x in payload]
            return " ".join(parts).lower()
        return str(payload).lower()
    except Exception:
        return ""


def _heuristic_tags_for_tool(payload_text: str) -> Dict[str, Any]:
    """
    Heuristics for tool executions.
    Returns:
        {
          "risk_level": int,
          "tags": List[str],
          "reasons": str,
        }
    """
    risk_level = 1
    tags: List[str] = []
    reasons: List[str] = []

    text = payload_text

    # Filesystem operations
    fs_keywords = [
        "rm -rf",
        "rm ",
        "delete ",
        "del ",
        "remove(",
        "unlink(",
        "os.remove",
        "os.rmdir",
        "shutil.rmtree",
        "open(",
        "write(",
        "truncate",
        "chmod",
        "chown",
        "format ",
        "mkfs",
        "drop table",
    ]
    if any(k in text for k in fs_keywords):
        risk_level = max(risk_level, 3)
        tags.append("filesystem")
        reasons.append("Potential filesystem modification (delete/write).")

    # Network / HTTP
    net_keywords = [
        "http://",
        "https://",
        "requests.",
        "curl ",
        "wget ",
        "socket.",
        "ftp://",
        "tcp://",
        "udp://",
    ]
    if any(k in text for k in net_keywords):
        risk_level = max(risk_level, 3)
        tags.append("network")
        reasons.append("Potential network / HTTP access.")

    # Shell / subprocess
    shell_keywords = [
        "subprocess.",
        "os.system",
        "sh -c",
        "bash -c",
        "powershell ",
        "cmd.exe",
        "shell=True",
    ]
    if any(k in text for k in shell_keywords):
        risk_level = max(risk_level, 4)
        tags.append("shell")
        reasons.append("Potential shell / subprocess execution.")

    # System / privileged hints
    system_keywords = [
        "sudo ",
        "runas ",
        "regedit",
        "hklm\\",
        "schtasks",
        "taskkill",
        "service ",
        "sc.exe",
    ]
    if any(k in text for k in system_keywords):
        risk_level = max(risk_level, 5)
        tags.append("system")
        reasons.append("Potential privileged / system-level action.")

    if not reasons:
        reasons.append("No sensitive patterns detected; treated as minor risk.")

    return {
        "risk_level": int(risk_level),
        "tags": sorted(set(tags)),
        "reasons": " ".join(reasons),
    }


def assess_risk(kind: str, payload: Any) -> Dict[str, Any]:
    """
    Public entrypoint: assess risk for a given operation.

    Args:
        kind:  "tool", "code", etc. (currently mainly "tool")
        payload: free-form data describing the operation. For tools,
                 this should include tool name + args.

    Returns:
        {
          "risk_level": int (1–6),
          "tags": List[str],
          "reasons": str,
          "kind": str,
        }

    MUST NOT RAISE.
    """
    try:
        text = _normalize_text(payload)
        if not text:
            return {
                "risk_level": 1,
                "tags": [],
                "reasons": "Empty payload; defaulting to MINOR risk.",
                "kind": kind,
            }

        if kind == "tool":
            info = _heuristic_tags_for_tool(text)
        else:
            # For now, reuse tool heuristics for other kinds too;
            # can be specialized later.
            info = _heuristic_tags_for_tool(text)

        info["kind"] = kind
        return info

    except Exception:
        # Absolutely must never break callers.
        return {
            "risk_level": 1,
            "tags": [],
            "reasons": "Risk assessment failed; defaulting to MINOR risk.",
            "kind": kind,
        }
