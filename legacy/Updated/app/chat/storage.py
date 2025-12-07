"""
Chat storage layer.

Stores chat messages per chat_id in a simple in-memory dictionary for V1.
Later can be swapped to SQLite / Redis without changing router or UI.
"""

from typing import Dict, List, Any
from threading import Lock

# { chat_id: [ { "sender": "user"/"assistant", "content": "..." }, ... ] }
_CHAT_LOGS: Dict[str, List[Dict[str, Any]]] = {}
_lock = Lock()


def append_message(chat_id: str, sender: str, content: str) -> None:
    """
    Add a message to a chat.
    """
    if not chat_id:
        return
    entry = {"sender": sender, "content": content}
    with _lock:
        _CHAT_LOGS.setdefault(chat_id, []).append(entry)


def get_messages(chat_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Return up to the last `limit` messages of one chat.
    """
    if not chat_id:
        return []
    with _lock:
        msgs = _CHAT_LOGS.get(chat_id, [])
        return msgs[-limit:].copy()


def clear_chat(chat_id: str) -> None:
    """
    Remove all messages from a chat.
    """
    if not chat_id:
        return
    with _lock:
        _CHAT_LOGS.pop(chat_id, None)
