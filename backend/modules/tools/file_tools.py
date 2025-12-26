"""
file_tools.py

Tools for file operations and Knowledge Base (KB) interaction.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 🟢 FIX: Use absolute import for profile_kb
try:
    from backend.modules.kb.profile_kb import add_snippet, list_snippets, get_snippet, search_snippets
except ImportError:
    # Fallback/Mock if the module isn't strictly available in some contexts
    def add_snippet(*args, **kwargs): return {"error": "KB module missing"}
    def list_snippets(*args, **kwargs): return {"snippets": []}
    def get_snippet(*args, **kwargs): return None
    def search_snippets(*args, **kwargs): return {"snippets": []}


# =========================
# Security Configuration
# =========================

# Define allowed base directories for file operations
# Only files within these directories can be accessed
ALLOWED_BASE_DIRS = [
    # Current working directory and subdirectories
    Path.cwd(),
    # Backend directory for configuration files
    Path(__file__).parent.parent.parent,  # Points to backend/
]

def _validate_file_path(requested_path: str) -> tuple[bool, str, Path | None]:
    """
    Validate and normalize a file path for security.

    Returns:
        (is_valid, error_message, resolved_path)
    """
    if not requested_path or not isinstance(requested_path, str):
        return False, "Invalid path: empty or non-string", None

    # Convert to Path object for cross-platform handling
    try:
        path = Path(requested_path)
    except Exception as e:
        logger.warning(f"Failed to parse path '{requested_path}': {e}")
        return False, "Invalid path format", None

    # Resolve the path to handle symlinks, relative components, etc.
    try:
        resolved_path = path.resolve()
    except (OSError, RuntimeError) as e:
        logger.warning(f"Failed to resolve path '{requested_path}': {e}")
        return False, f"Cannot resolve path: {e}", None

    # Check for directory traversal (even after resolution)
    # This catches cases where .. components resolve to outside allowed dirs
    try:
        resolved_str = str(resolved_path)
        if ".." in resolved_str:
            logger.warning(f"Directory traversal detected in resolved path: {resolved_str}")
            return False, "Directory traversal not allowed", None
    except Exception:
        # If we can't check the string representation, be conservative
        return False, "Path validation failed", None

    # Check if path is within allowed directories
    allowed = False
    for base_dir in ALLOWED_BASE_DIRS:
        try:
            # Use relative path to check containment
            resolved_path.relative_to(base_dir)
            allowed = True
            break
        except ValueError:
            continue  # Not within this base directory

    if not allowed:
        allowed_dirs_str = ", ".join(str(d) for d in ALLOWED_BASE_DIRS)
        logger.warning(f"Access denied: path '{resolved_path}' not within allowed directories: {allowed_dirs_str}")
        return False, f"Access denied: path outside allowed directories", None

    # Additional security checks
    # Prevent access to hidden files/directories (starting with .) except common dev directories
    blocked_hidden_parts = []
    for part in resolved_path.parts:
        if part.startswith('.'):
            # Allow common development directories
            allowed_hidden = {'.git', '.vscode', '.idea', '.pytest_cache', '__pycache__'}
            if part not in allowed_hidden:
                blocked_hidden_parts.append(part)

    if blocked_hidden_parts:
        logger.warning(f"Access denied: hidden directory not allowed: {resolved_path} (blocked: {blocked_hidden_parts})")
        return False, "Access denied: hidden files not allowed", None

    # Prevent access to Windows device files
    if os.name == 'nt':
        filename = resolved_path.name.upper()
        if filename in ('CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                       'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                       'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'):
            logger.warning(f"Access denied: Windows device file not allowed: {resolved_path}")
            return False, "Access denied: device files not allowed", None

    # Prevent access to NTFS alternate streams
    if os.name == 'nt' and ':' in resolved_path.name:
        logger.warning(f"Access denied: NTFS alternate stream not allowed: {resolved_path}")
        return False, "Access denied: alternate streams not allowed", None

    return True, "", resolved_path

def tool_read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reads the content of a file.
    Args:
      - path (str): The file path to read.
    """
    path = args.get("path")
    if not path:
        return {"ok": False, "message": "Missing 'path' argument."}

    # Robust security validation
    is_valid, error_msg, resolved_path = _validate_file_path(path)
    if not is_valid or resolved_path is None:
        logger.warning(f"File read blocked: {error_msg} (requested: {path})")
        return {"ok": False, "message": error_msg}

    try:
        if not resolved_path.exists():
            return {"ok": False, "message": f"File not found: {path}"}

        if not resolved_path.is_file():
            return {"ok": False, "message": f"Not a file: {path}"}

        with open(resolved_path, "r", encoding="utf-8") as f:
            content = f.read()

        return {"ok": True, "content": content, "path": str(resolved_path)}
    except PermissionError:
        logger.warning(f"Permission denied reading file: {resolved_path}")
        return {"ok": False, "message": "Permission denied"}
    except UnicodeDecodeError as e:
        logger.warning(f"Encoding error reading file {resolved_path}: {e}")
        return {"ok": False, "message": "File encoding not supported"}
    except Exception as e:
        logger.error(f"Unexpected error reading file {resolved_path}: {e}")
        return {"ok": False, "message": f"Read failed: {e}"}

def tool_write_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Writes content to a file.
    Args:
      - path (str): The file path.
      - content (str): The text content to write.
    """
    path = args.get("path")
    content = args.get("content")
    if not path or content is None:
        return {"ok": False, "message": "Missing 'path' or 'content'."}

    # Validate content is a string
    if not isinstance(content, str):
        return {"ok": False, "message": "Content must be a string."}

    # Robust security validation
    is_valid, error_msg, resolved_path = _validate_file_path(path)
    if not is_valid or resolved_path is None:
        logger.warning(f"File write blocked: {error_msg} (requested: {path})")
        return {"ok": False, "message": error_msg}

    try:
        # Ensure parent directory exists
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        with open(resolved_path, "w", encoding="utf-8") as f:
            f.write(content)

        return {"ok": True, "message": f"File written: {str(resolved_path)}"}
    except PermissionError:
        logger.warning(f"Permission denied writing file: {resolved_path}")
        return {"ok": False, "message": "Permission denied"}
    except OSError as e:
        logger.error(f"OS error writing file {resolved_path}: {e}")
        return {"ok": False, "message": f"Write failed: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error writing file {resolved_path}: {e}")
        return {"ok": False, "message": f"Write failed: {e}"}

# --- KB Tools Wrappers ---

def tool_kb_add(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Add a snippet to the Knowledge Base.
    Args:
      - title (str): Title of the note.
      - content (str): The content/body.
      - tags (str): Comma-separated tags.
    """
    profile_id = context.get("profile_id") if context else None
    if not profile_id:
        return {"ok": False, "message": "No profile context provided for KB operation."}

    return add_snippet(
        profile_id=profile_id,
        title=args.get("title", "Untitled"),
        content=args.get("content", ""),
        tags=args.get("tags", "")
    )

def tool_kb_search(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Search the Knowledge Base.
    Args:
      - query (str): Search term.
    """
    profile_id = context.get("profile_id") if context else None
    if not profile_id:
        return {"ok": False, "message": "No profile context provided."}

    return search_snippets(
        profile_id=profile_id,
        query=args.get("query", "")
    )

def tool_kb_list(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    List recent KB snippets.
    """
    profile_id = context.get("profile_id") if context else None
    if not profile_id:
        return {"ok": False, "message": "No profile context provided."}

    return list_snippets(profile_id=profile_id, limit=args.get("limit", 10))


TOOL_REGISTRY = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "kb_add": tool_kb_add,
    "kb_search": tool_kb_search,
    "kb_list": tool_kb_list,
}