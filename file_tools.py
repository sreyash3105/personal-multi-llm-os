"""
Simple "tool" functions the chat model can call via the bridge.

For now they mostly work as wrappers around the profile knowledge base:
- create_profile_note
- list_profile_notes
- read_profile_note

Each tool:
- takes a dict of arguments
- returns a dict with at least: {"ok": bool, "message": str, ...}
"""

from typing import Dict, Any, List

from profile_kb import add_snippet, list_snippets, get_snippet


def tool_create_profile_note(args: Dict[str, Any]) -> Dict[str, Any]:
    profile_id = (args.get("profile_id") or "").strip()
    title = (args.get("title") or "").strip()
    content = (args.get("content") or "").strip()

    if not profile_id:
        return {"ok": False, "message": "Missing profile_id"}
    if not title or not content:
        return {"ok": False, "message": "Both title and content are required"}

    note_id = add_snippet(profile_id, title, content)
    if not note_id:
        return {"ok": False, "message": "Failed to create note"}

    return {
        "ok": True,
        "message": f"Created note #{note_id} for profile {profile_id} with title '{title}'.",
        "note_id": note_id,
    }


def tool_list_profile_notes(args: Dict[str, Any]) -> Dict[str, Any]:
    profile_id = (args.get("profile_id") or "").strip()
    if not profile_id:
        return {"ok": False, "message": "Missing profile_id"}

    notes = list_snippets(profile_id, limit=int(args.get("limit") or 20))

    if not notes:
        return {
            "ok": True,
            "message": f"No notes found for profile {profile_id}.",
            "notes": [],
        }

    lines: List[str] = []
    for n in notes:
        preview = (n["content"] or "").strip().splitlines()
        preview_line = preview[0] if preview else ""
        if len(preview_line) > 120:
            preview_line = preview_line[:117] + "..."
        lines.append(f"#{n['id']} · {n['title']} · {preview_line}")

    return {
        "ok": True,
        "message": "Profile notes:\n" + "\n".join(lines),
        "notes": notes,
    }


def tool_read_profile_note(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        return {"ok": False, "message": "Invalid or missing note_id"}

    note = get_snippet(note_id)
    if not note:
        return {"ok": False, "message": f"No note found with id {note_id}"}

    return {
        "ok": True,
        "message": f"Note #{note_id} - {note['title']}:\n\n{note['content']}",
        "note": note,
    }


TOOL_REGISTRY = {
    "create_profile_note": tool_create_profile_note,
    "list_profile_notes": tool_list_profile_notes,
    "read_profile_note": tool_read_profile_note,
}
