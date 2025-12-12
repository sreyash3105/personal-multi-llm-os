"""
file_tools.py

Tools for file operations and Knowledge Base (KB) interaction.
"""

import os
import shutil
from typing import Dict, Any, List, Optional

# 🟢 FIX: Use absolute import for profile_kb
try:
    from backend.modules.kb.profile_kb import add_snippet, list_snippets, get_snippet, search_snippets
except ImportError:
    # Fallback/Mock if the module isn't strictly available in some contexts
    def add_snippet(*args, **kwargs): return {"error": "KB module missing"}
    def list_snippets(*args, **kwargs): return {"snippets": []}
    def get_snippet(*args, **kwargs): return None
    def search_snippets(*args, **kwargs): return {"snippets": []}

def tool_read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reads the content of a file.
    Args:
      - path (str): The file path to read.
    """
    path = args.get("path")
    if not path:
        return {"ok": False, "message": "Missing 'path' argument."}
    
    # Basic security check (prevent directory traversal)
    if ".." in path or path.startswith("/"):
        return {"ok": False, "message": "Access denied: Absolute paths or '..' not allowed."}

    try:
        if not os.path.exists(path):
            return {"ok": False, "message": f"File not found: {path}"}
            
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"ok": True, "content": content, "path": path}
    except Exception as e:
        return {"ok": False, "message": str(e)}

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

    # Basic security check
    if ".." in path or path.startswith("/"):
        return {"ok": False, "message": "Access denied."}

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "message": f"File written: {path}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

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