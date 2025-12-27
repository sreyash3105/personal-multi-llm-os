"""
policy_table.py (D2-Step-1)

Canonical policy table for declarative scope → auth level mapping.
No enforcement, no wildcards, no inheritance.
Fail-closed for unknown scopes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict
import sqlite3
from datetime import datetime

# Database setup
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
POLICY_DB_PATH = DATA_DIR / "policy.sqlite3"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(POLICY_DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except sqlite3.DatabaseError:
        pass
    return conn


def _init_db() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_mappings (
                scope TEXT PRIMARY KEY,
                min_auth_level INTEGER NOT NULL,
                description TEXT,
                reason TEXT,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()


# Initialize on import
_init_db()


def get_required_auth_level(scope: str) -> int:
    """
    Get required auth level for a scope.
    Fail-closed: returns 6 (BLOCK) for unknown scopes.
    """
    with _get_conn() as conn:
        cur = conn.execute("""
            SELECT min_auth_level FROM policy_mappings WHERE scope = ?
        """, (scope,))
        row = cur.fetchone()
        return row["min_auth_level"] if row else 6  # BLOCK


def create_policy(
    scope: str,
    min_auth_level: int,
    description: str = "",
    reason: str = "",
) -> bool:
    """
    Create a new policy mapping.
    """
    if not scope or not isinstance(min_auth_level, int) or not (1 <= min_auth_level <= 6):
        return False

    now = datetime.utcnow().isoformat()
    try:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO policy_mappings
                (scope, min_auth_level, description, reason, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (scope, min_auth_level, description, reason, now, now))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Scope exists


def update_policy(
    scope: str,
    min_auth_level: Optional[int] = None,
    description: Optional[str] = None,
    reason: Optional[str] = None,
) -> bool:
    """
    Update an existing policy mapping.
    Increments version.
    """
    updates = []
    params = []
    if min_auth_level is not None:
        if not (1 <= min_auth_level <= 6):
            return False
        updates.append("min_auth_level = ?")
        params.append(min_auth_level)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if reason is not None:
        updates.append("reason = ?")
        params.append(reason)

    if not updates:
        return False

    updates.append("version = version + 1")
    updates.append("updated_at = ?")
    params.extend([datetime.utcnow().isoformat(), scope])

    with _get_conn() as conn:
        cur = conn.execute(f"""
            UPDATE policy_mappings
            SET {', '.join(updates)}
            WHERE scope = ?
        """, params)
        success = cur.rowcount > 0
        conn.commit()
        return success


def get_policy(scope: str) -> Optional[Dict]:
    """
    Get policy details for a scope.
    """
    with _get_conn() as conn:
        cur = conn.execute("""
            SELECT * FROM policy_mappings WHERE scope = ?
        """, (scope,))
        row = cur.fetchone()
        if row:
            return {
                "scope": row["scope"],
                "min_auth_level": row["min_auth_level"],
                "description": row["description"],
                "reason": row["reason"],
                "version": row["version"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        return None


def list_policies() -> List[Dict]:
    """
    List all policy mappings.
    """
    with _get_conn() as conn:
        cur = conn.execute("""
            SELECT * FROM policy_mappings ORDER BY scope
        """)
        rows = cur.fetchall()
        return [
            {
                "scope": row["scope"],
                "min_auth_level": row["min_auth_level"],
                "description": row["description"],
                "reason": row["reason"],
                "version": row["version"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]