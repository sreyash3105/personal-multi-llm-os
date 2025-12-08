"""
Per-profile knowledge base (simple SQLite backend).

- Stores short text snippets per profile (notes, decisions, specs).
- Used by chat to build extra context for a given profile.

This is intentionally minimal for V1:
- Single table: profile_snippets
- Basic operations: insert, list, build_context

HARDENING BASE:
- SQLite connection hardened with WAL journaling, NORMAL sync, and a sensible timeout.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# DB file lives in the same directory as this script, under "data/"
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "profile_kb.sqlite3"


def _get_conn() -> sqlite3.Connection:
    """
    Open a SQLite connection with:
    - row_factory = Row
    - WAL journal mode for better durability under concurrent access
    - synchronous = NORMAL for a good safety/speed balance
    - a reasonable timeout to reduce 'database is locked' errors.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except sqlite3.DatabaseError:
        # If PRAGMAs fail, continue with defaults instead of breaking.
        pass

    return conn


def _init_db() -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile_snippets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              profile_id TEXT NOT NULL,
              title TEXT NOT NULL,
              content TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


# Initialize schema at import time
_init_db()


def add_snippet(profile_id: str, title: str, content: str) -> int:
    """
    Create a new snippet for a profile.
    Returns the inserted row ID (or 0 on validation failure).
    """
    profile_id = (profile_id or "").strip()
    title = (title or "").strip()
    content = (content or "").strip()

    if not profile_id or not title or not content:
        return 0

    now = datetime.now().isoformat(timespec="seconds")
    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO profile_snippets (profile_id, title, content, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (profile_id, title, content, now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def update_snippet(snippet_id: int, new_content: str) -> bool:
    """
    Replace the content of an existing snippet.
    """
    new_content = (new_content or "").strip()
    if not new_content:
        return False

    now = datetime.now().isoformat(timespec="seconds")
    with _get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE profile_snippets
            SET content = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_content, now, snippet_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_snippet(snippet_id: int) -> bool:
    """
    Delete a snippet by ID.
    Returns True if a row was removed, False otherwise.
    """
    with _get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM profile_snippets WHERE id = ?",
            (int(snippet_id),),
        )
        conn.commit()
        return cur.rowcount > 0


def list_snippets(profile_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Return recent snippets for a profile (newest first).
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return []

    with _get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, profile_id, title, content, created_at, updated_at
            FROM profile_snippets
            WHERE profile_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (profile_id, int(limit)),
        )
        rows = cur.fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "profile_id": r["profile_id"],
                "title": r["title"],
                "content": r["content"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
        )
    return out


def search_snippets(profile_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Lightweight search over profile snippets.

    Behaviour (V1, stable):
    - If profile_id is empty -> return [].
    - If query is empty/whitespace -> returns recent snippets (same as list_snippets, capped by limit).
    - Otherwise:
        - Fetch a slightly larger recent window.
        - Do a simple keyword match over title + content.
        - Return up to `limit` matching snippets (newest first).

    This is intentionally simple and non-embedding-based for V3.6.x.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return []

    query = (query or "").strip().lower()
    if not query:
        # No query -> just recent snippets
        return list_snippets(profile_id, limit=limit)

    words = [w for w in query.replace(",", " ").split() if len(w) > 2]
    if not words:
        # Query only had tiny tokens; fall back to recent snippets
        return list_snippets(profile_id, limit=limit)

    # Fetch a slightly larger pool to filter from.
    base = list_snippets(profile_id, limit=limit * 3)

    if not base:
        return []

    filtered: List[Dict[str, Any]] = []
    for s in base:
        text = f"{s.get('title', '')} {s.get('content', '')}".lower()
        if any(w in text for w in words):
            filtered.append(s)

    return filtered[:limit]


def get_snippet(snippet_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a single snippet by ID.
    """
    with _get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, profile_id, title, content, created_at, updated_at
            FROM profile_snippets
            WHERE id = ?
            """,
            (int(snippet_id),),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "profile_id": row["profile_id"],
        "title": row["title"],
        "content": row["content"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def build_profile_context(profile_id: str, query: str, max_snippets: int = 8) -> str:
    """
    Build a plain-text context block for a given profile.

    For V1:
    - Just takes the most recent N snippets for that profile.
    - Light keyword filter on `query` if present.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return ""

    snippets = list_snippets(profile_id, limit=max_snippets * 2)

    if not snippets:
        return ""

    # Tiny relevance filter: keep snippets that mention at least one query word
    query = (query or "").strip().lower()
    if query:
        words = [w for w in query.replace(",", " ").split() if len(w) > 2]
        if words:
            filtered = []
            for s in snippets:
                text = (s["title"] + " " + s["content"]).lower()
                if any(w in text for w in words):
                    filtered.append(s)
            if filtered:
                snippets = filtered[:max_snippets]

    snippets = snippets[:max_snippets]
    if not snippets:
        return ""

    blocks: List[str] = []
    for s in snippets:
        blocks.append(
            f"[KB NOTE #{s['id']} - {s['title']}]\n{s['content'].strip()}"
        )

    return "\n\n".join(blocks)


# =========================
# Preview helper for UI (read-only)
# =========================

def build_profile_preview(profile_id: str, limit: int = 20) -> Dict[str, Any]:
    """
    Build a lightweight preview payload for a profile's KB.

    Returned shape (stable for UI):

        {
          "profile_id": "A",
          "total": 3,
          "snippets": [
            {
              "id": 1,
              "title": "Note title",
              "preview": "First line of note...",
              "created_at": "...",
              "updated_at": "...",
            },
            ...
          ],
        }
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return {"profile_id": "", "total": 0, "snippets": []}

    snippets = list_snippets(profile_id, limit=limit)
    items: List[Dict[str, Any]] = []

    for s in snippets:
        content = (s.get("content") or "").strip()
        first_line = content.splitlines()[0] if content else ""
        if len(first_line) > 160:
            first_line = first_line[:157] + "..."
        items.append(
            {
                "id": s["id"],
                "title": s["title"],
                "preview": first_line,
                "created_at": s["created_at"],
                "updated_at": s["updated_at"],
            }
        )

    return {
        "profile_id": profile_id,
        "total": len(items),
        "snippets": items,
    }
