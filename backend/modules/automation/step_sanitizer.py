# backend/modules/automation/step_sanitizer.py
"""
Step sanitizer for automation plans (BCMM Automation Layer).

Purpose
-------
- Inspect planned steps (the planner's JSON) and either approve them
  or reject them with clear reasons.
- Provide safe defaults and easy configuration for allowed directories,
  allowed tools, and disallowed command patterns.
- Prevent obvious destructive operations from being executed without
  explicit admin approval.

Usage
-----
from backend.modules.automation.step_sanitizer import sanitize_steps, SanitizationError

try:
    clean_steps = sanitize_steps(plan["steps"], allowlist_dirs=["C:\\Temp", "/tmp"], allowed_tools=["write_file", "open_file"])
except SanitizationError as e:
    # reject / ask for approval / show warning to user
    print("Plan rejected:", e)
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

# ---- Configuration ----
# Edit these defaults to match your environment & security policy.

# Paths that are allowed for file operations by default.
DEFAULT_ALLOWED_DIRS = [
    r"C:\Temp",
    r"C:\Users",  # careful - will be checked for subpath
    "/tmp",
    "/home",
]

# Disallowed (critical) directories which should NEVER be written to by automation.
DEFAULT_BLOCKED_DIRS = [
    r"C:\Windows",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\Users\Default",
    "/etc",
    "/bin",
    "/sbin",
    "/usr",
    "/boot",
]

# Allowed tool names - unless explicitly listed here, tool calls are rejected in strict mode.
DEFAULT_ALLOWED_TOOLS = [
    "write_file",
    "append_file",
    "read_file",
    "open_file",
    "create_dir",
    "list_dir",
    "copy_file",
    "move_file",
    "click",
    "keyboard",
    "shell_safe",  # wrapper for very restricted shell actions
]

# Patterns that obviously indicate destructive shell commands or dangerous tokens.
DANGEROUS_CMD_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\brmdir\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\bdd\b",
    r"\bmkfs\b",
    r"\brm\s+-f\b",
    r":\s*>",  # redirection into a file (could be used maliciously)
    r"\bdel\s+/s\b",
    r"\bsc\s+delete\b",
    r"\breg\s+delete\b",
]

# File extensions considered potentially dangerous to execute/write (executables, system DLLs).
BLOCKED_EXTENSIONS = [".sys", ".dll", ".exe", ".msi", ".bat", ".cmd", ".scr"]

# ---- Exceptions ----


class SanitizationError(Exception):
    """Raised when steps fail safety checks."""


# ---- Helpers ----


def _normalize_path(p: str) -> str:
    if not p:
        return p
    # Expand user and vars, then get absolute normalized path
    try:
        expanded = os.path.expandvars(os.path.expanduser(p))
        norm = os.path.normpath(expanded)
        return norm
    except Exception:
        return p


def _is_subpath(child: str, parent: str) -> bool:
    """
    Return True if 'child' is inside 'parent' directory (or equals).
    Works for Windows and POSIX paths; both must be normalized.
    """
    try:
        child_norm = os.path.abspath(child).lower()
        parent_norm = os.path.abspath(parent).lower()
        # add trailing sep to parent for exact matching
        if not parent_norm.endswith(os.path.sep):
            parent_norm = parent_norm + os.path.sep
        return child_norm.startswith(parent_norm) or child_norm == parent_norm.rstrip(os.path.sep)
    except Exception:
        return False


def _matches_dangerous_pattern(cmd: str) -> Optional[str]:
    """Return matching pattern if cmd matches any dangerous regex."""
    if not cmd:
        return None
    for pat in DANGEROUS_CMD_PATTERNS:
        if re.search(pat, cmd, flags=re.IGNORECASE):
            return pat
    return None


def _has_blocked_extension(path: str) -> bool:
    low = (path or "").lower()
    for ext in BLOCKED_EXTENSIONS:
        if low.endswith(ext):
            return True
    return False


# ---- Sanitizers ----


def sanitize_step(
    step: Dict,
    allowlist_dirs: Optional[List[str]] = None,
    allowed_tools: Optional[List[str]] = None,
    blocked_dirs: Optional[List[str]] = None,
) -> Dict:
    """
    Inspect & sanitize a single step.
    Returns the original step (possibly normalized).
    Raises SanitizationError on rejection.

    step expected shape:
      {
        "id": "s1",
        "action": "tool" | "file" | "shell" | "click" | "keyboard" | "note",
        "tool": "write_file",
        "args": { ... },
        "description": "..."
      }
    """

    allowlist_dirs = allowlist_dirs or DEFAULT_ALLOWED_DIRS
    allowed_tools = allowed_tools or DEFAULT_ALLOWED_TOOLS
    blocked_dirs = blocked_dirs or DEFAULT_BLOCKED_DIRS

    action = (step.get("action") or "").strip().lower()
    tool = (step.get("tool") or "").strip()
    args = step.get("args") or {}

    # Normalize common fields
    cleaned = dict(step)
    if "args" in cleaned and isinstance(cleaned["args"], dict):
        cleaned_args = dict(cleaned["args"])
        # normalize path args commonly used: path, dest, source, file, filename
        for k in ("path", "dest", "destination", "source", "file", "filename"):
            if k in cleaned_args and isinstance(cleaned_args[k], str):
                cleaned_args[k] = _normalize_path(cleaned_args[k])
        cleaned["args"] = cleaned_args

    # Action-specific checks
    if action in ("file", "tool"):
        # If tool present, ensure allowed
        if tool:
            if tool not in allowed_tools:
                raise SanitizationError(f"Tool '{tool}' is not in allowed tools list.")
        # For file actions expect a path
        path_keys = [k for k in ("path", "dest", "destination", "file", "filename", "source") if k in cleaned["args"]]
        if path_keys:
            for key in path_keys:
                p = cleaned["args"].get(key)
                if not p or not isinstance(p, str):
                    raise SanitizationError(f"Step missing required path argument '{key}'.")
                norm = _normalize_path(p)
                # block suspicious extensions
                if _has_blocked_extension(norm):
                    raise SanitizationError(f"Blocked file extension for path: {norm}")
                # block system directories
                for b in blocked_dirs:
                    if _is_subpath(norm, b):
                        raise SanitizationError(f"Path {norm} is inside blocked directory {b}.")
                # allow only if inside one of allowlist dirs OR is under user's home (optionally)
                allowed = False
                for a in allowlist_dirs:
                    try:
                        if _is_subpath(norm, a):
                            allowed = True
                            break
                    except Exception:
                        continue
                # allow under profile home directory as a special case
                home = os.path.expanduser("~")
                try:
                    if _is_subpath(norm, home):
                        allowed = True
                except Exception:
                    pass
                if not allowed:
                    raise SanitizationError(f"Path {norm} is not within allowed directories: {allowlist_dirs} or home.")
        else:
            # If no path provided, require tool being in allowed list and args harmless
            if not tool:
                raise SanitizationError("File/tool action requires a 'tool' or a path argument.")

    elif action == "shell":
        # Shell commands are risky — inspect for dangerous patterns
        cmd = cleaned["args"].get("cmd") or cleaned["args"].get("command") or ""
        if not cmd or not isinstance(cmd, str):
            raise SanitizationError("Shell action requires a 'cmd' string argument.")
        # check dangerous substrings / patterns
        pat = _matches_dangerous_pattern(cmd)
        if pat:
            raise SanitizationError(f"Shell command matches dangerous pattern '{pat}'. Command refused.")
        # also block redirections to system paths
        if re.search(r">>\s*/|>\s*/", cmd):
            raise SanitizationError("Shell redirection to root or absolute paths is blocked.")
        # small additional check: extremely long single-line commands (likely injected)
        if len(cmd) > 4000:
            raise SanitizationError("Shell command too long / suspicious.")

    elif action in ("keyboard", "click"):
        # these actions are UI-driven; ensure args have safe numeric coordinates or selectors
        coords_ok = True
        if "x" in cleaned["args"] or "y" in cleaned["args"]:
            try:
                x = float(cleaned["args"].get("x", 0))
                y = float(cleaned["args"].get("y", 0))
            except Exception:
                coords_ok = False
            if not coords_ok:
                raise SanitizationError("Invalid coordinates in click/keyboard action.")
        # if selector-based ensure selector is a short string
        if "selector" in cleaned["args"]:
            sel = cleaned["args"]["selector"]
            if not isinstance(sel, str) or len(sel) > 300:
                raise SanitizationError("Invalid UI selector in action.")
    elif action == "note":
        # always safe
        pass
    else:
        raise SanitizationError(f"Unknown or unsupported action '{action}' in step id={step.get('id')}")

    return cleaned


def sanitize_steps(
    steps: List[Dict],
    allowlist_dirs: Optional[List[str]] = None,
    allowed_tools: Optional[List[str]] = None,
    blocked_dirs: Optional[List[str]] = None,
    fail_fast: bool = True,
) -> List[Dict]:
    """
    Sanitize a list of steps. Returns the sanitized list or raises SanitizationError.

    Parameters:
      - steps: list of step dicts (planner output)
      - allowlist_dirs: directories that are allowed for file ops
      - allowed_tools: list of allowed tool names
      - blocked_dirs: directories always blocked
      - fail_fast: if True, raise on first error; else collect errors and raise aggregated message
    """
    if not isinstance(steps, list):
        raise SanitizationError("Steps must be a list of step objects.")

    allowlist_dirs = allowlist_dirs or DEFAULT_ALLOWED_DIRS
    allowed_tools = allowed_tools or DEFAULT_ALLOWED_TOOLS
    blocked_dirs = blocked_dirs or DEFAULT_BLOCKED_DIRS

    sanitized: List[Dict] = []
    errors: List[Tuple[int, str]] = []

    for idx, s in enumerate(steps):
        try:
            clean = sanitize_step(s, allowlist_dirs=allowlist_dirs, allowed_tools=allowed_tools, blocked_dirs=blocked_dirs)
            sanitized.append(clean)
        except SanitizationError as e:
            errors.append((idx, str(e)))
            if fail_fast:
                raise SanitizationError(f"Step #{idx} rejected: {e}") from e
            # else continue collecting errors

    if errors:
        msgs = "; ".join([f"#{i}:{m}" for i, m in errors])
        raise SanitizationError(f"One or more steps rejected: {msgs}")

    return sanitized
