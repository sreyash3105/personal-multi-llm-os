"""
permission_scopes.py (Phase C2, Step 5)

Canonical permission scope taxonomy.
Flat, explicit, human-readable scopes for all privileged operations.
No wildcards, no inheritance, no dynamic generation.

Scopes describe intent, not permission.
"""

from __future__ import annotations

# File operations
SCOPE_FILE_READ = "file.read"
SCOPE_FILE_WRITE = "file.write"
SCOPE_FILE_DELETE = "file.delete"

# Tool execution (prefix for dynamic tool names)
SCOPE_TOOL_EXEC_PREFIX = "tool.exec"

# System operations
SCOPE_SYSTEM_CONFIG = "system.config"

# Example full scopes for known tools (for reference)
SCOPE_TOOL_EXEC_SHELL = f"{SCOPE_TOOL_EXEC_PREFIX}.shell"
SCOPE_TOOL_EXEC_NETWORK = f"{SCOPE_TOOL_EXEC_PREFIX}.network"
SCOPE_TOOL_PING = f"{SCOPE_TOOL_EXEC_PREFIX}.ping"

# Function to build tool scope (for dynamic tools)
def build_tool_scope(tool_name: str) -> str:
    """
    Build a canonical tool execution scope.
    No validation; just formatting.
    """
    return f"{SCOPE_TOOL_EXEC_PREFIX}.{tool_name}"