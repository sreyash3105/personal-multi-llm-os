"""
STRICT PROCESS CAPABILITY

Capability: process.spawn
No inference. No defaults. Refusal-first.

Build Prompt: CAPABILITY EXPANSION UNDER MEK
"""

from __future__ import annotations

import subprocess
import os
import shlex
from typing import Dict, Any, Set, Optional, List
from dataclasses import dataclass
from enum import Enum


class ProcessRefusal(Enum):
    EXECUTABLE_NOT_ALLOWED = "executable_not_allowed"
    TIMEOUT_EXCEEDED = "timeout_exceeded"
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"
    SHELL_INVOCATION_FORBIDDEN = "shell_invocation_forbidden"
    MISSING_EXECUTABLE = "missing_executable"
    MISSING_ARGS = "missing_args"


class ProcessError(RuntimeError):
    def __init__(self, refusal: ProcessRefusal, details: str):
        self.refusal = refusal
        self.details = details
        super().__init__(f"[{refusal.value}] {details}")


ALLOWED_EXECUTABLES: Set[str] = {
    "/usr/bin/python3",
    "/usr/bin/python",
    "/usr/local/bin/python3",
    "/usr/local/bin/python",
    "python3",
    "python",
}

MAX_TIMEOUT_SECONDS = 60
MAX_OUTPUT_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class ProcessConfig:
    allowed_executables: Set[str] = ALLOWED_EXECUTABLES.copy()
    max_timeout_seconds: int = MAX_TIMEOUT_SECONDS
    max_output_bytes: int = MAX_OUTPUT_BYTES
    forbid_shell: bool = True
    forbid_environment_inheritance: bool = True


def validate_executable_allowed(
    executable_path: str,
    config: ProcessConfig,
) -> None:
    if not executable_path:
        raise ProcessError(
            ProcessRefusal.MISSING_EXECUTABLE,
            "Executable path required"
        )

    if not os.path.isabs(executable_path):
        if executable_path in config.allowed_executables:
            return
    else:
        for allowed in config.allowed_executables:
            if executable_path == allowed:
                return

    raise ProcessError(
        ProcessRefusal.EXECUTABLE_NOT_ALLOWED,
        f"Executable not allowed: {executable_path}"
    )


def validate_timeout(timeout: int, config: ProcessConfig) -> None:
    if timeout <= 0:
        raise ProcessError(
            ProcessRefusal.TIMEOUT_EXCEEDED,
            f"Timeout must be positive: {timeout}"
        )

    if timeout > config.max_timeout_seconds:
        raise ProcessError(
            ProcessRefusal.TIMEOUT_EXCEEDED,
            f"Timeout {timeout}s exceeds limit {config.max_timeout_seconds}s"
        )


def validate_output_size(output: bytes, config: ProcessConfig) -> None:
    if len(output) > config.max_output_bytes:
        raise ProcessError(
            ProcessRefusal.OUTPUT_LIMIT_EXCEEDED,
            f"Output size {len(output)} exceeds limit {config.max_output_bytes}"
        )


def build_env(
    base_env: Any,
    config: ProcessConfig,
    allowed_vars: Optional[Set[str]] = None,
) -> Dict[str, str]:
    if config.forbid_environment_inheritance:
        return {}

    env = {}
    if allowed_vars:
        for var in allowed_vars:
            if var in base_env:
                env[var] = base_env[var]
    else:
        env = dict(base_env)

    return env


class ProcessSpawn:
    consequence_level = "HIGH"
    required_fields = ["executable", "args"]

    @staticmethod
    def execute(
        context: Dict[str, Any],
        config: Optional[ProcessConfig] = None,
    ) -> Dict[str, Any]:
        config = config or ProcessConfig()

        executable = context.get("executable")
        if not executable:
            raise ProcessError(
                ProcessRefusal.MISSING_EXECUTABLE,
                "Executable field required"
            )

        args = context.get("args")
        if args is None:
            raise ProcessError(
                ProcessRefusal.MISSING_ARGS,
                "Args field required"
            )

        if not isinstance(args, list):
            raise ProcessError(
                ProcessRefusal.MISSING_ARGS,
                "Args must be a list"
            )

        validate_executable_allowed(executable, config)

        timeout = context.get("timeout", 30)
        validate_timeout(timeout, config)

        capture_output = context.get("capture_output", True)
        working_dir = context.get("working_dir")

        cmd = [executable] + args

        env = build_env(os.environ, config)

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                capture_output=capture_output,
                text=True if capture_output else False,
                timeout=timeout,
                env=env or None,
                cwd=working_dir,
            )

            if capture_output:
                stdout_bytes = result.stdout.encode("utf-8")
                stderr_bytes = result.stderr.encode("utf-8")
                validate_output_size(stdout_bytes, config)
                validate_output_size(stderr_bytes, config)

            return {
                "returncode": result.returncode,
                "stdout": result.stdout if capture_output else None,
                "stderr": result.stderr if capture_output else None,
                "timeout": timeout,
                "executable": executable,
                "args": args,
            }
        except subprocess.TimeoutExpired:
            raise ProcessError(
                ProcessRefusal.TIMEOUT_EXCEEDED,
                f"Process timed out after {timeout}s"
            )
        except FileNotFoundError:
            raise ProcessError(
                ProcessRefusal.EXECUTABLE_NOT_ALLOWED,
                f"Executable not found: {executable}"
            )
        except Exception as e:
            raise ProcessError(
                ProcessRefusal.EXECUTABLE_NOT_ALLOWED,
                f"Failed to spawn process: {e}"
            )
