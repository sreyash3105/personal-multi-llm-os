"""
Process execution capability - controlled system interaction.

Whitelisted commands, explicit environment, output capture.
"""

from __future__ import annotations

import subprocess
import os
from typing import Dict, Any, List, Optional, Set

from backend.core.capability import CapabilityDescriptor, ConsequenceLevel, create_refusal, RefusalReason


WHITELISTED_COMMANDS: Set[str] = {
    "python",
    "pip",
    "npm",
    "ls",
    "cat",
    "echo",
    "cd",
    "pwd",
    "dir",
}


class ProcessCapability:
    """
    Execute system commands with explicit constraints.
    """

    def __init__(self, whitelist: Optional[Set[str]] = None):
        self.whitelist = whitelist or WHITELISTED_COMMANDS

    def _validate_command(self, command: str, context: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate command against whitelist.
        """
        parts = command.split()
        if not parts:
            return False, "Empty command"

        base_command = parts[0]

        if base_command in self.whitelist:
            return True, ""

        return False, f"Command not whitelisted: {base_command}"

    def execute_command(self, context: Dict[str, Any]) -> Any:
        """
        Execute a system command.
        """
        command = context.get("command")
        if not command:
            return create_refusal(
                RefusalReason.AMBIGUITY,
                "Command field required",
                "process.execute",
            )

        is_valid, reason = self._validate_command(command, context)
        if not is_valid:
            return create_refusal(
                RefusalReason.SCOPE_VIOLATION,
                reason,
                "process.execute",
            )

        print(f"[PROCESS] Executing: {command}")

        env = context.get("env", os.environ.copy())
        capture = context.get("capture_output", True)
        timeout = context.get("timeout", 60)

        try:
            if capture:
                result = subprocess.run(
                    command,
                    shell=True,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                return {
                    "status": "success",
                    "command": command,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            else:
                result = subprocess.run(
                    command,
                    shell=True,
                    env=env,
                    timeout=timeout,
                )
                return {
                    "status": "success",
                    "command": command,
                    "returncode": result.returncode,
                }
        except subprocess.TimeoutExpired:
            return create_refusal(
                RefusalReason.CONSTRAINT_VIOLATION,
                f"Command timed out after {timeout}s",
                "process.execute",
            )
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "command": command,
            }

    def list_processes(self, context: Dict[str, Any]) -> Any:
        """
        List running processes (read-only).
        """
        import psutil

        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "cmdline": ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else '',
                })
            return {
                "status": "success",
                "processes": processes,
                "count": len(processes),
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
            }


def create_process_capability() -> CapabilityDescriptor:
    """
    Create the process execution capability descriptor.
    """
    cap = ProcessCapability()

    def execute(context: Dict[str, Any]) -> Any:
        operation = context.get("operation", "execute")
        if operation == "list":
            return cap.list_processes(context)
        elif operation == "execute":
            return cap.execute_command(context)
        else:
            return create_refusal(
                RefusalReason.CONSTRAINT_VIOLATION,
                f"Unknown operation: {operation}",
                "process.execute",
            )

    return CapabilityDescriptor(
        name="process",
        scope="system",
        consequence_level=ConsequenceLevel.HIGH,
        required_context_fields=["operation", "command"],
        required_approvals=[],
        execute_fn=execute,
    )
