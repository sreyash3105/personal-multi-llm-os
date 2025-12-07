# chat_storage.py
"""
Persistent storage for multi-profile, multi-chat conversations.

Now backed by a local SQLite database instead of JSON files.

Schema:

  data/chat/chat.db

  profiles(
    id TEXT PRIMARY KEY,              -- "A", "B", "C", ...
    display_name TEXT NOT NULL,
    model_override TEXT,
    created_at TEXT NOT NULL          -- "07 Dec 2025, 05:42 PM"
  )

  chats(
    id TEXT NOT NULL,                 -- "a", "b", "aa", ...
    profile_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    model_override TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (id, profile_id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
  )

  messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    FOREIGN KEY (profile_id, chat_id)
      REFERENCES chats(profile_id, id) ON DELETE CASCADE
  )

Public API is kept compatible with the previous JSON implementation:

- list_profiles() -> List[Dict]
- get_profile(profile_id) -> Optional[Dict]
- create_profile(...)
- rename_profile(...)
- set_profile_model(...)
- delete_profile(...)

- list_chats(profile_id) -> List[Dict]
- create_chat(profile_id, ...)
- get_chat(profile_id, chat_id) -> Optional[Dict]
- rename_chat(...)
- set_chat_model(...)
- delete_chat(...)

- append_message(profile_id, chat_id, role, text)
- get_messages(profile_id, chat_id) -> List[Dict]

All timestamps are still WhatsApp-style strings.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "chat"
DB_PATH = DATA_DIR / "chat.db"


# =========================
# Helpers: filesystem + time
# =========================

def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _format_ts(dt: Optional[datetime] = None) -> str:
    """
    Format timestamp like WhatsApp-style:
    "07 Dec 2025, 05:42 PM"
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%d %b %Y, %I:%M %p")


def _next_alpha_id(existing: List[str], uppercase: bool = True) -> str:
    """
    Generate next ID in sequence:
    A..Z, AA..AZ..BA..ZZ.. etc for uppercase
    a..z, aa..zz.. for lowercase.

    existing: list of already used IDs
    """
    existing_set = set(existing)

    def to_str(n: int) -> str:
        # 1 -> A, 26 -> Z, 27 -> AA, ...
        letters = []
        while n > 0:
            n, rem = divmod(n - 1, 26)
            letters.append(chr(ord('A') + rem))
        s = "".join(reversed(letters))
        return s.upper() if uppercase else s.lower()

    n = 1
    while True:
        candidate = to_str(n)
        if candidate not in existing_set:
            return candidate
        n += 1


# =========================
# Helpers: DB connection & schema
# =========================

def _get_conn() -> sqlite3.Connection:
    """
    Open a SQLite connection with row_factory=Row and foreign_keys ON.
    """
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Ensure foreign keys (for cascades) are enforced on every connection.
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _init_db() -> None:
    """
    Create tables if they do not exist.
    Safe to call multiple times.
    """
    with _get_conn() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                model_override TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT NOT NULL,
                profile_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                model_override TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (id, profile_id),
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );
            """
        )

        cur.execute(
            """
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
            """
        )

        conn.commit()


# Initialize DB on module import
_init_db()


# =========================
# Helpers: row → dict
# =========================

def _profile_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "model_override": row["model_override"],
        "created_at": row["created_at"],
    }


def _chat_row_to_dict(row: sqlite3.Row, message_count: int = 0) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "model_override": row["model_override"],
        "created_at": row["created_at"],
        "message_count": int(message_count),
    }


# =========================
# Profiles
# =========================

def list_profiles() -> List[Dict[str, Any]]:
    """
    Return list of profiles:
    [
      {
        "id": "A",
        "display_name": "A",
        "model_override": null,
        "created_at": "...",
      },
      ...
    ]
    """
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, display_name, model_override, created_at "
            "FROM profiles ORDER BY created_at ASC, id ASC;"
        )
        rows = cur.fetchall()
    return [_profile_row_to_dict(r) for r in rows]


def get_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, display_name, model_override, created_at "
            "FROM profiles WHERE id = ?;",
            (profile_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return _profile_row_to_dict(row)


def create_profile(display_name: Optional[str] = None,
                   model_override: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new profile with next alpha ID: A..Z..AA.. etc.
    """
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM profiles;")
        existing_ids = [r["id"] for r in cur.fetchall()]

        new_id = _next_alpha_id(existing_ids, uppercase=True)

        if display_name is None or not display_name.strip():
            display_name = new_id

        created_at = _format_ts()

        cur.execute(
            """
            INSERT INTO profiles (id, display_name, model_override, created_at)
            VALUES (?, ?, ?, ?);
            """,
            (new_id, display_name, model_override, created_at),
        )
        conn.commit()

    return {
        "id": new_id,
        "display_name": display_name,
        "model_override": model_override,
        "created_at": created_at,
    }


def rename_profile(profile_id: str, new_display_name: str) -> bool:
    new_display_name = new_display_name.strip()
    if not new_display_name:
        # Keep old name if empty passed.
        prof = get_profile(profile_id)
        if not prof:
            return False
        new_display_name = prof["display_name"]

    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE profiles SET display_name = ? WHERE id = ?;",
            (new_display_name, profile_id),
        )
        conn.commit()
        return cur.rowcount > 0


def set_profile_model(profile_id: str, model_override: Optional[str]) -> bool:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE profiles SET model_override = ? WHERE id = ?;",
            (model_override, profile_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_profile(profile_id: str) -> bool:
    """
    Delete a profile and all its chats+messages from DB.
    """
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM profiles WHERE id = ?;", (profile_id,))
        conn.commit()
        return cur.rowcount > 0


# =========================
# Chats within a profile
# =========================

def list_chats(profile_id: str) -> List[Dict[str, Any]]:
    """
    List chats within a profile. Returns sorted by created_at ascending.
    Each item:
    {
      "id": "a",
      "display_name": "a",
      "model_override": null,
      "created_at": "...",
      "message_count": 0,
    }
    """
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              c.id,
              c.display_name,
              c.model_override,
              c.created_at,
              COALESCE(COUNT(m.id), 0) AS message_count
            FROM chats c
            LEFT JOIN messages m
              ON m.profile_id = c.profile_id AND m.chat_id = c.id
            WHERE c.profile_id = ?
            GROUP BY c.id, c.profile_id, c.display_name, c.model_override, c.created_at
            ORDER BY c.created_at ASC, c.id ASC;
            """,
            (profile_id,),
        )
        rows = cur.fetchall()

    return [_chat_row_to_dict(r, r["message_count"]) for r in rows]


def create_chat(profile_id: str,
                display_name: Optional[str] = None,
                model_override: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new chat within a profile.
    Chat IDs follow a..z..aa.. pattern (lowercase).
    """
    with _get_conn() as conn:
        cur = conn.cursor()

        # Ensure profile exists
        cur.execute("SELECT 1 FROM profiles WHERE id = ?;", (profile_id,))
        if not cur.fetchone():
            # Auto-create profile if missing (optional logic; matches old "auto-create" spirit)
            # You can change this to raise if you prefer strictness.
            prof = create_profile(display_name=None, model_override=None)
            if prof["id"] != profile_id:
                # If caller used a non-existing ID, we keep the requested profile_id behaviour simple:
                # just create a profile with that id manually.
                cur.execute(
                    "INSERT OR IGNORE INTO profiles (id, display_name, model_override, created_at) "
                    "VALUES (?, ?, ?, ?);",
                    (profile_id, profile_id, None, _format_ts()),
                )

        # Generate next chat ID within this profile
        cur.execute(
            "SELECT id FROM chats WHERE profile_id = ?;",
            (profile_id,),
        )
        existing_ids = [r["id"] for r in cur.fetchall()]
        new_id = _next_alpha_id(existing_ids, uppercase=False)

        if display_name is None or not display_name.strip():
            display_name = new_id

        created_at = _format_ts()

        cur.execute(
            """
            INSERT INTO chats (id, profile_id, display_name, model_override, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (new_id, profile_id, display_name, model_override, created_at),
        )
        conn.commit()

    return {
        "id": new_id,
        "display_name": display_name,
        "model_override": model_override,
        "created_at": created_at,
        "messages": [],
    }


def get_chat(profile_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
    """
    Return chat metadata + messages list (for compatibility with old JSON shape).
    """
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, profile_id, display_name, model_override, created_at
            FROM chats
            WHERE profile_id = ? AND id = ?;
            """,
            (profile_id, chat_id),
        )
        row = cur.fetchone()

        if not row:
            return None

        # Load messages
        cur.execute(
            """
            SELECT ts, role, text
            FROM messages
            WHERE profile_id = ? AND chat_id = ?
            ORDER BY id ASC;
            """,
            (profile_id, chat_id),
        )
        msg_rows = cur.fetchall()

    messages = [
        {"ts": m["ts"], "role": m["role"], "text": m["text"]}
        for m in msg_rows
    ]

    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "model_override": row["model_override"],
        "created_at": row["created_at"],
        "messages": messages,
    }


def rename_chat(profile_id: str, chat_id: str, new_display_name: str) -> bool:
    new_display_name = new_display_name.strip()
    if not new_display_name:
        chat = get_chat(profile_id, chat_id)
        if not chat:
            return False
        new_display_name = chat.get("display_name") or chat_id

    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE chats
            SET display_name = ?
            WHERE profile_id = ? AND id = ?;
            """,
            (new_display_name, profile_id, chat_id),
        )
        conn.commit()
        return cur.rowcount > 0


def set_chat_model(profile_id: str, chat_id: str, model_override: Optional[str]) -> bool:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE chats
            SET model_override = ?
            WHERE profile_id = ? AND id = ?;
            """,
            (model_override, profile_id, chat_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_chat(profile_id: str, chat_id: str) -> bool:
    """
    Delete a chat and all its messages.
    """
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM chats WHERE profile_id = ? AND id = ?;",
            (profile_id, chat_id),
        )
        conn.commit()
        return cur.rowcount > 0


# =========================
# Messages
# =========================

def append_message(profile_id: str, chat_id: str, role: str, text: str) -> None:
    """
    Append a message with WhatsApp-style timestamp.
    role: "user" or "assistant" (or system later).
    """
    # Ensure chat exists; if not, auto-create (matches previous behaviour).
    chat = get_chat(profile_id, chat_id)
    if not chat:
        created_chat = create_chat(profile_id=profile_id, display_name=chat_id)
        chat_id = created_chat["id"]

    ts = _format_ts()
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO messages (profile_id, chat_id, ts, role, text)
            VALUES (?, ?, ?, ?, ?);
            """,
            (profile_id, chat_id, ts, role, text),
        )
        conn.commit()


def get_messages(profile_id: str, chat_id: str) -> List[Dict[str, Any]]:
    with _get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ts, role, text
            FROM messages
            WHERE profile_id = ? AND chat_id = ?
            ORDER BY id ASC;
            """,
            (profile_id, chat_id),
        )
        rows = cur.fetchall()

    return [
        {"ts": r["ts"], "role": r["role"], "text": r["text"]}
        for r in rows
    ]
