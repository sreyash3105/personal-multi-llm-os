"""
STRICT FILESYSTEM CAPABILITIES

Separate capabilities: filesystem.read, filesystem.write, filesystem.delete
No inference. No defaults. Refusal-first.

Build Prompt: CAPABILITY EXPANSION UNDER MEK
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Set, Optional
from dataclasses import dataclass
from enum import Enum
import os


class FilesystemRefusal(Enum):
    PATH_NOT_EXPLICIT = "path_not_explicit"
    PATH_OUT_OF_SCOPE = "path_out_of_scope"
    FILE_TOO_LARGE = "file_too_large"
    TYPE_NOT_ALLOWED = "type_not_allowed"
    PATH_IS_SYMLINK = "path_is_symlink"
    IS_DIRECTORY = "is_directory"
    FILE_NOT_FOUND = "file_not_found"


class FilesystemError(RuntimeError):
    def __init__(self, refusal: FilesystemRefusal, details: str):
        self.refusal = refusal
        self.details = details
        super().__init__(f"[{refusal.value}] {details}")


ALLOWED_MIME_TYPES: Set[str] = {
    "text/plain",
    "text/html",
    "application/json",
    "application/xml",
    "text/csv",
    "text/markdown",
}

MAX_FILE_SIZE = 10 * 1024 * 1024


@dataclass(frozen=True)
class FilesystemConfig:
    max_file_size: int = MAX_FILE_SIZE
    allowed_mime_types: Set[str] = ALLOWED_MIME_TYPES.copy()
    allowed_directories: Set[str] = set()
    forbid_symlinks: bool = True


def validate_path_is_absolute(path_str: str) -> None:
    if not path_str:
        raise FilesystemError(
            FilesystemRefusal.PATH_NOT_EXPLICIT,
            "Path is empty"
        )
    if not os.path.isabs(path_str):
        raise FilesystemError(
            FilesystemRefusal.PATH_NOT_EXPLICIT,
            f"Path must be absolute: {path_str}"
        )


def validate_path_in_scope(path: Path, config: FilesystemConfig) -> None:
    if not config.allowed_directories:
        return

    path_str = str(path.resolve())
    for allowed_dir in config.allowed_directories:
        if path_str.startswith(allowed_dir):
            return

    raise FilesystemError(
        FilesystemRefusal.PATH_OUT_OF_SCOPE,
        f"Path outside allowed directories: {path_str}"
    )


def validate_not_symlink(path: Path, config: FilesystemConfig) -> None:
    if config.forbid_symlinks and path.is_symlink():
        raise FilesystemError(
            FilesystemRefusal.PATH_IS_SYMLINK,
            f"Symlinks forbidden: {path}"
        )


def validate_file_size(path: Path, config: FilesystemConfig) -> None:
    if not path.exists() or not path.is_file():
        return

    size = path.stat().st_size
    if size > config.max_file_size:
        raise FilesystemError(
            FilesystemRefusal.FILE_TOO_LARGE,
            f"File size {size} exceeds limit {config.max_file_size}: {path}"
        )


class FilesystemRead:
    consequence_level = "LOW"
    required_fields = ["path"]

    @staticmethod
    def execute(context: Dict[str, Any], config: Optional[FilesystemConfig] = None) -> Dict[str, Any]:
        config = config or FilesystemConfig()

        path_str = context.get("path")
        if not path_str:
            raise FilesystemError(
                FilesystemRefusal.PATH_NOT_EXPLICIT,
                "Path field required"
            )

        validate_path_is_absolute(path_str)

        path = Path(path_str)

        if not path.exists():
            raise FilesystemError(
                FilesystemRefusal.FILE_NOT_FOUND,
                f"File not found: {path}"
            )

        if path.is_dir():
            raise FilesystemError(
                FilesystemRefusal.IS_DIRECTORY,
                f"Path is directory, not file: {path}"
            )

        validate_path_in_scope(path, config)
        validate_not_symlink(path, config)
        validate_file_size(path, config)

        try:
            content = path.read_text(encoding="utf-8")
            return {
                "content": content,
                "size": len(content),
                "path": str(path),
            }
        except Exception as e:
            raise FilesystemError(
                FilesystemRefusal.TYPE_NOT_ALLOWED,
                f"Failed to read file: {e}"
            )


class FilesystemWrite:
    consequence_level = "HIGH"
    required_fields = ["path", "content"]

    @staticmethod
    def execute(context: Dict[str, Any], config: Optional[FilesystemConfig] = None) -> Dict[str, Any]:
        config = config or FilesystemConfig()

        path_str = context.get("path")
        if not path_str:
            raise FilesystemError(
                FilesystemRefusal.PATH_NOT_EXPLICIT,
                "Path field required"
            )

        content = context.get("content")
        if content is None:
            raise FilesystemError(
                FilesystemRefusal.PATH_NOT_EXPLICIT,
                "Content field required"
            )

        if len(content) > config.max_file_size:
            raise FilesystemError(
                FilesystemRefusal.FILE_TOO_LARGE,
                f"Content size {len(content)} exceeds limit {config.max_file_size}"
            )

        validate_path_is_absolute(path_str)

        path = Path(path_str)

        if path.is_symlink():
            raise FilesystemError(
                FilesystemRefusal.PATH_IS_SYMLINK,
                f"Cannot write to symlink: {path}"
            )

        validate_path_in_scope(path, config)

        if path.exists() and path.is_dir():
            raise FilesystemError(
                FilesystemRefusal.IS_DIRECTORY,
                f"Path is directory, not file: {path}"
            )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {
                "size": len(content),
                "path": str(path),
            }
        except Exception as e:
            raise FilesystemError(
                FilesystemRefusal.TYPE_NOT_ALLOWED,
                f"Failed to write file: {e}"
            )


class FilesystemDelete:
    consequence_level = "HIGH"
    required_fields = ["path"]

    @staticmethod
    def execute(context: Dict[str, Any], config: Optional[FilesystemConfig] = None) -> Dict[str, Any]:
        config = config or FilesystemConfig()

        path_str = context.get("path")
        if not path_str:
            raise FilesystemError(
                FilesystemRefusal.PATH_NOT_EXPLICIT,
                "Path field required"
            )

        validate_path_is_absolute(path_str)

        path = Path(path_str)

        if not path.exists():
            return {
                "deleted": False,
                "path": str(path),
                "reason": "file_not_found",
            }

        if path.is_dir():
            raise FilesystemError(
                FilesystemRefusal.IS_DIRECTORY,
                f"Recursive delete forbidden (directory): {path}"
            )

        if path.is_symlink():
            raise FilesystemError(
                FilesystemRefusal.PATH_IS_SYMLINK,
                f"Cannot delete symlink: {path}"
            )

        validate_path_in_scope(path, config)

        try:
            path.unlink()
            return {
                "deleted": True,
                "path": str(path),
            }
        except Exception as e:
            raise FilesystemError(
                FilesystemRefusal.TYPE_NOT_ALLOWED,
                f"Failed to delete file: {e}"
            )
