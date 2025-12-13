# backend/modules/chat/chat_storage.py
"""
Persistent storage for multi-profile chats.
Rewritten for path safety and robust SQLite handling.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# --- 1. Absolute Path Setup ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "chat"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "chat.db"

print(f"[CHAT_STORAGE] DB Path: {DB_PATH}")

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
    except sqlite3.DatabaseError:
        pass
    return conn

def _init_db() -> None:
    with _get_conn() as conn:
        # Profiles table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                model_override TEXT,
                created_at TEXT NOT NULL
            );
        """)
        # Chats table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT NOT NULL,
                profile_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                model_override TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (id, profile_id),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );
        """)
        # Messages table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY (profile_id, chat_id)
                    REFERENCES chats(profile_id, id) ON DELETE CASCADE
            );
        """)
        conn.commit()

_init_db()

# --- 2. Helpers ---

def _fmt_ts() -> str:
    return datetime.now().strftime("%d %b %Y, %I:%M %p")

def _next_id(existing_ids: List[str], uppercase: bool = False) -> str:
    """Generate simple IDs like 'a', 'b', 'z', 'aa'."""
    existing = set(existing_ids)
    n = 1
    while True:
        # simple base-26 generation logic for short IDs
        chars = []
        temp = n
        while temp > 0:
            temp, rem = divmod(temp - 1, 26)
            chars.append(chr(rem + (65 if uppercase else 97)))
        candidate = "".join(reversed(chars))
        if candidate not in existing:
            return candidate
        n += 1

# --- 3. Profile Operations ---

def list_profiles() -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM profiles ORDER BY created_at ASC").fetchall()
    return [dict(r) for r in rows]

def get_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return dict(row) if row else None

def create_profile(display_name: str = None, model_override: str = None) -> Dict[str, Any]:
    with _get_conn() as conn:
        existing = [r["id"] for r in conn.execute("SELECT id FROM profiles").fetchall()]
        new_id = _next_id(existing, uppercase=True)
        display_name = display_name or new_id
        created_at = _fmt_ts()
        
        conn.execute(
            "INSERT INTO profiles (id, display_name, model_override, created_at) VALUES (?, ?, ?, ?)",
            (new_id, display_name, model_override, created_at)
        )
        conn.commit()
        return {"id": new_id, "display_name": display_name, "model_override": model_override, "created_at": created_at}

def rename_profile(profile_id: str, new_name: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("UPDATE profiles SET display_name = ? WHERE id = ?", (new_name, profile_id))
        conn.commit()
        return cur.rowcount > 0

def set_profile_model(profile_id: str, model: Optional[str]) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("UPDATE profiles SET model_override = ? WHERE id = ?", (model, profile_id))
        conn.commit()
        return cur.rowcount > 0

def delete_profile(profile_id: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        conn.commit()
        return cur.rowcount > 0

# --- 4. Chat Operations ---

def list_chats(profile_id: str) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chats WHERE profile_id = ? ORDER BY created_at ASC", 
            (profile_id,)
        ).fetchall()
    return [dict(r) for r in rows]

def get_chat(profile_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM chats WHERE profile_id = ? AND id = ?", 
            (profile_id, chat_id)
        ).fetchone()
    return dict(row) if row else None

def create_chat(profile_id: str, display_name: str = None, model_override: str = None) -> Dict[str, Any]:
    # Ensure profile exists
    if not get_profile(profile_id):
        create_profile(display_name=profile_id) # Auto-create fallback

    with _get_conn() as conn:
        existing = [r["id"] for r in conn.execute("SELECT id FROM chats WHERE profile_id = ?", (profile_id,)).fetchall()]
        new_id = _next_id(existing, uppercase=False)
        display_name = display_name or new_id
        created_at = _fmt_ts()

        conn.execute(
            "INSERT INTO chats (id, profile_id, display_name, model_override, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id, profile_id, display_name, model_override, created_at)
        )
        conn.commit()
        return {"id": new_id, "profile_id": profile_id, "display_name": display_name, "created_at": created_at}

def rename_chat(profile_id: str, chat_id: str, new_name: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE chats SET display_name = ? WHERE profile_id = ? AND id = ?",
            (new_name, profile_id, chat_id)
        )
        conn.commit()
        return cur.rowcount > 0

def set_chat_model(profile_id: str, chat_id: str, model: Optional[str]) -> bool:
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE chats SET model_override = ? WHERE profile_id = ? AND id = ?",
            (model, profile_id, chat_id)
        )
        conn.commit()
        return cur.rowcount > 0

def delete_chat(profile_id: str, chat_id: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM chats WHERE profile_id = ? AND id = ?",
            (profile_id, chat_id)
        )
        conn.commit()
        return cur.rowcount > 0

# --- 5. Message Operations ---

def append_message(profile_id: str, chat_id: str, role: str, text: str) -> None:
    # Auto-create chat if missing
    if not get_chat(profile_id, chat_id):
        create_chat(profile_id, display_name=chat_id)
    
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (profile_id, chat_id, ts, role, text) VALUES (?, ?, ?, ?, ?)",
            (profile_id, chat_id, _fmt_ts(), role, text)
        )
        conn.commit()

def get_messages(profile_id: str, chat_id: str) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT ts, role, text FROM messages WHERE profile_id = ? AND chat_id = ? ORDER BY id ASC",
            (profile_id, chat_id)
        ).fetchall()
    return [dict(r) for r in rows]