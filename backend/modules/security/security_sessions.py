from __future__ import annotations

"""
security_sessions.py

V3.5 — Security System (Phase 2)
--------------------------------
SQLite-backed storage for temporary security authorizations.

Purpose:
- When a user approves a risky action via a UI popup, we create a
  short-lived "security session" that allows that operation (or class
  of operations) to proceed without asking again within a grace period.

Design:
- Lives in its own SQLite DB: data/security_sessions.sqlite3
- Hardened connection (WAL, timeout) similar to profile_kb.py.
- Simple, explicit API; no FastAPI or UI dependencies.

Schema:
  data/security_sessions.sqlite3

  security_sessions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    scope TEXT NOT NULL,        -- e.g. "tool:delete_file", "tool:*", "op:tool_call"
    auth_level INTEGER NOT NULL, -- required SecurityAuthLevel (1..6) approved
    secret TEXT,                 -- optional phrase/hash for high-risk approvals
    created_at TEXT NOT NULL,    -- ISO timestamp
    expires_at TEXT NOT NULL,    -- ISO timestamp
    used_count INTEGER NOT NULL DEFAULT 0,
    max_uses INTEGER NOT NULL DEFAULT 1
  )

Notes:
- "scope" is a free-form string; the caller decides what it means.
  For example:
    - "tool:delete_file"
    - "tool:*" (any tool for this profile)
    - "op:tool_call"
- We treat sessions as consumable permits:
    - only valid if NOW < expires_at
    - only valid if used_count < max_uses
    - auth_level must be >= required_level for the operation.

Typical flow (for /api/security/auth):
1) Frontend requests an approval challenge for a specific operation.
2) Once user approves (YES/NO or password/phrase), backend calls
   create_security_session(...).
3) When executing a risky tool, tools_runtime (or wrapper) calls
   consume_security_session_if_allowed(...) before enforcing a block.

This module has NO side effects beyond managing its own DB.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# DB location (separate from chat/history DBs)
# Always store DB in <project_root>/data/ regardless of this file's location.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "security_sessions.sqlite"


# =========================
# Low-level helpers
# =========================

def _get_conn() -> sqlite3.Connection:
    """
    Open a hardened SQLite connection:

    - WAL journal mode for better durability under concurrent access.
    - synchronous = NORMAL for safety/speed balance.
    - row_factory = Row for convenient dict conversion.
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
    """
    Initialize the security_sessions table.
    Safe to call multiple times (IF NOT EXISTS).
    """
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS security_sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              profile_id TEXT NOT NULL,
              scope TEXT NOT NULL,
              auth_level INTEGER NOT NULL,
              secret TEXT,
              created_at TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              used_count INTEGER NOT NULL DEFAULT 0,
              max_uses INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_security_sessions_profile_scope
            ON security_sessions (profile_id, scope);
            """
        )
        conn.commit()


# Initialize schema at import time.
_init_db()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "profile_id": row["profile_id"],
        "scope": row["scope"],
        "auth_level": row["auth_level"],
        "secret": row["secret"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "used_count": row["used_count"],
        "max_uses": row["max_uses"],
    }


def _now() -> datetime:
    return datetime.utcnow()


# =========================
# Public API
# =========================

def create_security_session(
    *,
    profile_id: str,
    scope: str,
    auth_level: int,
    ttl_seconds: int = 300,
    max_uses: int = 1,
    secret: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new temporary security session.

    Parameters:
      profile_id:
        Profile key (e.g. "A", UUID). Must be non-empty.

      scope:
        Free-form string describing what this approves:
          - "tool:delete_file"
          - "tool:*"
          - "op:tool_call"
        Caller is responsible for choosing consistent scopes.

      auth_level:
        SecurityAuthLevel value (1..6) that this approval covers.
        The session can be used for any operation that requires
        <= auth_level for this profile+scope.

      ttl_seconds:
        Time-to-live in seconds. Default = 300 (5 minutes).

      max_uses:
        How many times this approval can be consumed. Default = 1.

      secret:
        Optional phrase/hash used for high-risk approvals (auth_level >= 5).
        This module stores it as a raw string; hashing/verification is
        up to the caller.

    Returns:
      Dict representing the created session.
    """
    profile_id = (profile_id or "").strip()
    scope = (scope or "").strip()
    if not profile_id or not scope:
        raise ValueError("profile_id and scope must be non-empty strings.")

    auth_level_required = auth_level  # For compatibility

    now = _now()
    expires_at = now + timedelta(seconds=int(ttl_seconds))

    created_str = now.isoformat(timespec="seconds")
    expires_str = expires_at.isoformat(timespec="seconds")

    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO security_sessions (
              profile_id, scope, auth_level, secret,
              created_at, expires_at, used_count, max_uses
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (profile_id, scope, int(auth_level), secret, created_str, expires_str, int(max_uses)),
        )
        conn.commit()
        session_id = int(cur.lastrowid)

        cur2 = conn.execute(
            """
            SELECT id, profile_id, scope, auth_level, secret,
                   created_at, expires_at, used_count, max_uses
            FROM security_sessions
            WHERE id = ?
            """,
            (session_id,),
        )
        row = cur2.fetchone()

    if not row:
        raise RuntimeError("Failed to retrieve newly created security session.")

    return _row_to_dict(row)


def get_active_sessions_for_profile(
    profile_id: str,
    *,
    include_expired: bool = False,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Inspect active (or all) sessions for a given profile.

    This is primarily for debugging / future dashboard integration.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return []

    now_str = _now().isoformat(timespec="seconds")

    with _get_conn() as conn:
        if include_expired:
            cur = conn.execute(
                """
                SELECT id, profile_id, scope, auth_level, secret,
                       created_at, expires_at, used_count, max_uses
                FROM security_sessions
                WHERE profile_id = ?
                ORDER BY expires_at DESC, id DESC
                LIMIT ?
                """,
                (profile_id, int(limit)),
            )
        else:
            cur = conn.execute(
                """
                SELECT id, profile_id, scope, auth_level, secret,
                       created_at, expires_at, used_count, max_uses
                FROM security_sessions
                WHERE profile_id = ?
                  AND expires_at > ?
                  AND used_count < max_uses
                ORDER BY expires_at ASC, id ASC
                LIMIT ?
                """,
                (profile_id, now_str, int(limit)),
            )
        rows = cur.fetchall()

    return [_row_to_dict(r) for r in rows]


def consume_security_session_if_allowed(
    *,
    profile_id: str,
    scope: str,
    required_level: int,
    auth_level_required: Optional[int] = None,  # For compatibility
) -> Optional[Dict[str, Any]]:
    """
    Attempt to consume a security session for the given profile/scope.

    Logic:
      - Find the oldest session for this profile+scope where:
          auth_level >= required_level
          expires_at > now
          used_count < max_uses
      - Increment used_count by 1 atomically.
      - Return the updated session as a dict.

    If no suitable session exists, returns None.

    This function is intended to be called by enforcement code around
    tools / system actions:

        session = consume_security_session_if_allowed(
            profile_id=profile_id,
            scope=f"tool:{tool_name}",
            required_level=auth_level_required,
        )
        if session is None:
            # no valid approval; must block or request auth
        else:
            # proceed with operation; session has been consumed
    """
    profile_id = (profile_id or "").strip()
    scope = (scope or "").strip()
    if not profile_id or not scope:
        return None

    now_str = _now().isoformat(timespec="seconds")

    with _get_conn() as conn:
        # Atomic update: increment used_count only if it hasn't reached max_uses
        cur = conn.execute(
            """
            UPDATE security_sessions
            SET used_count = used_count + 1
            WHERE id = (
                SELECT id
                FROM security_sessions
                WHERE profile_id = ?
                  AND scope = ?
                  AND auth_level >= ?
                  AND expires_at > ?
                  AND used_count < max_uses
                ORDER BY expires_at ASC, id ASC
                LIMIT 1
            )
            RETURNING id, profile_id, scope, auth_level, secret,
                      created_at, expires_at, used_count, max_uses
            """,
            (profile_id, scope, int(required_level), now_str),
        )
        row = cur.fetchone()
        if not row:
            return None

        conn.commit()

    return _row_to_dict(row)


def cleanup_expired_sessions(max_rows: int = 500) -> int:
    """
    Best-effort cleanup of expired sessions.

    Returns the number of rows deleted.

    This can be called periodically (e.g. at startup or via a
    lightweight maintenance endpoint) to keep the table small.
    """
    now_str = _now().isoformat(timespec="seconds")

    with _get_conn() as conn:
        cur = conn.execute(
            """
            DELETE FROM security_sessions
            WHERE expires_at <= ?
            LIMIT ?
            """,
            (now_str, int(max_rows)),
        )
        deleted = cur.rowcount or 0
        conn.commit()

    return int(deleted)

# ==========================================
# SECURITY ENFORCEMENT EXTENSION (V3.6)
# ==========================================

from typing import Optional

# Lookup strongest unexpired session for this scope (non-consuming)
def sec_get_best_session_for_scope(*, profile_id: str, scope: str, required_level: int) -> Optional[dict]:
    profile_id = (profile_id or "").strip()
    scope = (scope or "").strip()
    if not profile_id or not scope:
        return None

    now_str = datetime.utcnow().isoformat(timespec="seconds")
    with _get_conn() as conn:
        cur = conn.execute(
            """
            SELECT *
            FROM security_sessions
            WHERE profile_id = ?
              AND scope = ?
              AND auth_level >= ?
              AND expires_at > ?
              AND used_count < max_uses
            ORDER BY auth_level DESC, expires_at ASC, id ASC
            LIMIT 1
            """,
            (profile_id, scope, int(required_level), now_str),
        )
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


# Unified check / consume helper for tools_runtime enforcement
def sec_check_or_consume(
    *,
    profile_id: str,
    scope: str,
    required_level: int,
    consume: bool = True,
) -> Optional[dict]:
    if consume:
        return consume_security_session_if_allowed(
            profile_id=profile_id,
            scope=scope,
            required_level=required_level,
        )
    return sec_get_best_session_for_scope(
        profile_id=profile_id,
        scope=scope,
        required_level=required_level,
    )


# Wildcard authorization for global tool approval
def sec_has_tool_wildcard(*, profile_id: str, required_level: int) -> bool:
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return False
    now_str = datetime.utcnow().isoformat(timespec="seconds")
    with _get_conn() as conn:
        cur = conn.execute(
            """
            SELECT 1
            FROM security_sessions
            WHERE profile_id = ?
              AND scope = 'tool:*'
              AND auth_level >= ?
              AND expires_at > ?
              AND used_count < max_uses
            LIMIT 1
            """,
            (profile_id, int(required_level), now_str),
        )
        return bool(cur.fetchone())
# ==========================================
# EXPORT ALIASES FOR BACKWARD COMPATIBILITY
# ==========================================

# legacy name expected by security_engine
try:
    get_best_session_for_scope = sec_get_best_session_for_scope
except NameError:
    # function not defined? (should never happen)
    pass
