"""
Filesystem capability - read/write operations.

Strict path scoping, explicit allowlist, high-consequence friction.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

from backend.core.capability import CapabilityDescriptor, ConsequenceLevel, create_refusal, RefusalReason
from backend.core.config import DATA_DIR


DEFAULT_ALLOWLIST: Set[str] = {
    "project",
    "data",
    "config",
    "logs",
}


class FilesystemCapability:
    """
    Filesystem operations with explicit constraints.
    """

    def __init__(self, allowlist: Optional[Set[str]] = None):
        self.allowlist = allowlist or DEFAULT_ALLOWLIST

    def _resolve_path(self, path_str: str, context: Dict[str, Any]) -> Optional[Path]:
        """
        Resolve and validate path.
        Returns None if path is outside allowlist.
        """
        try:
            path = Path(path_str).resolve()
        except Exception:
            return None

        path_str = str(path)

        for allowed_dir in self.allowlist:
            if path_str.startswith(allowed_dir):
                return path

        return None

    def _check_write_safety(self, path: Path, context: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if write operation is safe.
        Returns (is_safe, reason).
        """
        if not path.exists():
            return True, ""

        file_size = path.stat().st_size if path.is_file() else 0
        max_size = context.get("max_file_size", 10 * 1024 * 1024)

        if file_size > max_size:
            return False, f"File too large ({file_size} > {max_size} bytes)"

        return True, ""

    def read_file(self, path: str, context: Dict[str, Any]) -> Any:
        """
        Read file contents.
        """
        resolved_path = self._resolve_path(path, context)
        if not resolved_path:
            return create_refusal(
                RefusalReason.SCOPE_VIOLATION,
                f"Path outside allowlist: {path}",
                "filesystem.read",
            )

        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                "status": "success",
                "path": str(resolved_path),
                "content": content,
                "size": len(content),
            }
        except IOError as e:
            return {
                "status": "failed",
                "error": str(e),
                "path": str(resolved_path),
            }

    def write_file(self, path: str, content: str, context: Dict[str, Any]) -> Any:
        """
        Write file contents with safety checks.
        """
        resolved_path = self._resolve_path(path, context)
        if not resolved_path:
            return create_refusal(
                RefusalReason.SCOPE_VIOLATION,
                f"Path outside allowlist: {path}",
                "filesystem.write",
            )

        is_safe, reason = self._check_write_safety(resolved_path, context)
        if not is_safe:
            return create_refusal(
                RefusalReason.CONSTRAINT_VIOLATION,
                f"Write unsafe: {reason}",
                "filesystem.write",
            )

        print(f"[FILESYSTEM] Writing to {resolved_path}")

        try:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            with open(resolved_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {
                "status": "success",
                "path": str(resolved_path),
                "size": len(content),
            }
        except IOError as e:
            return {
                "status": "failed",
                "error": str(e),
                "path": str(resolved_path),
            }

    def list_directory(self, path: str, context: Dict[str, Any]) -> Any:
        """
        List directory contents.
        """
        resolved_path = self._resolve_path(path, context)
        if not resolved_path:
            return create_refusal(
                RefusalReason.SCOPE_VIOLATION,
                f"Path outside allowlist: {path}",
                "filesystem.list",
            )

        if not resolved_path.is_dir():
            return create_refusal(
                RefusalReason.CONSTRAINT_VIOLATION,
                f"Not a directory: {path}",
                "filesystem.list",
            )

        try:
            items = [str(p) for p in resolved_path.iterdir()]
            return {
                "status": "success",
                "path": str(resolved_path),
                "items": items,
                "count": len(items),
            }
        except IOError as e:
            return {
                "status": "failed",
                "error": str(e),
                "path": str(resolved_path),
            }

    def delete_file(self, path: str, context: Dict[str, Any]) -> Any:
        """
        Delete file (non-recursive).
        Recursive deletes are FORBIDDEN.
        """
        resolved_path = self._resolve_path(path, context)
        if not resolved_path:
            return create_refusal(
                RefusalReason.SCOPE_VIOLATION,
                f"Path outside allowlist: {path}",
                "filesystem.delete",
            )

        if not resolved_path.exists():
            return {
                "status": "success",
                "path": str(resolved_path),
                "deleted": False,
            }

        if resolved_path.is_dir():
            return create_refusal(
                RefusalReason.CONSTRAINT_VIOLATION,
                f"Recursive delete forbidden (directory): {path}",
                "filesystem.delete",
            )

        try:
            resolved_path.unlink()
            print(f"[FILESYSTEM] Deleted {resolved_path}")
            return {
                "status": "success",
                "path": str(resolved_path),
                "deleted": True,
            }
        except IOError as e:
            return {
                "status": "failed",
                "error": str(e),
                "path": str(resolved_path),
            }


def create_filesystem_capability() -> CapabilityDescriptor:
    """
    Create the filesystem capability descriptor.
    """
    cap = FilesystemCapability()

    def execute(context: Dict[str, Any]) -> Any:
        operation = context.get("operation", "read")
        path = context.get("path")
        content = context.get("content")

        if operation == "read":
            return cap.read_file(path, context)
        elif operation == "write":
            if content is None:
                return create_refusal(
                    RefusalReason.AMBIGUITY,
                    "Write operation requires 'content' field",
                    "filesystem.write",
                )
            return cap.write_file(path, content, context)
        elif operation == "list":
            return cap.list_directory(path, context)
        elif operation == "delete":
            return cap.delete_file(path, context)
        else:
            return create_refusal(
                RefusalReason.CONSTRAINT_VIOLATION,
                f"Unknown operation: {operation}",
                "filesystem.execute",
            )

    return CapabilityDescriptor(
        name="filesystem",
        scope="io",
        consequence_level=ConsequenceLevel.HIGH,
        required_context_fields=["operation", "path"],
        required_approvals=[],
        execute_fn=execute,
    )
