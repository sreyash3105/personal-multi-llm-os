"""
approvals.py (Phase C2, Step 2)

Explicit approval objects for temporary, ephemeral authority.
Approvals are data artifacts representing human-granted permissions.
No enforcement, no consumption, no blocking.

Approval objects:
- Represent explicit, bounded authority
- Are profile-scoped
- Decay by TTL
- Must be consumed explicitly (later steps)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import sqlite3

# Database setup (reuse pattern from permission_manager.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
APPROVALS_DB_PATH = DATA_DIR / "approvals.sqlite3"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(APPROVALS_DB_PATH), timeout=30.0)
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
            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                auth_level INTEGER NOT NULL,
                issued_by TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                max_uses INTEGER NOT NULL,
                used_count INTEGER NOT NULL DEFAULT 0,
                revoked_at TEXT
            )
        """)
        # Add revoked_at if missing (migration)
        try:
            conn.execute("ALTER TABLE approvals ADD COLUMN revoked_at TEXT")
        except sqlite3.OperationalError:
            pass  # Column exists
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_approvals_profile_active
            ON approvals (profile_id, expires_at)
        """)
        conn.commit()


# Initialize on import
_init_db()


@dataclass
class Approval:
    """
    Explicit approval artifact.
    Represents temporary authority granted by human intent.
    """
    id: Optional[int]
    profile_id: str
    scope: str
    auth_level: int
    issued_by: str
    issued_at: datetime
    expires_at: datetime
    max_uses: int
    used_count: int
    revoked_at: Optional[datetime]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "scope": self.scope,
            "auth_level": self.auth_level,
            "issued_by": self.issued_by,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "max_uses": self.max_uses,
            "used_count": self.used_count,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


def _row_to_approval(row: sqlite3.Row) -> Approval:
    return Approval(
        id=row["id"],
        profile_id=row["profile_id"],
        scope=row["scope"],
        auth_level=row["auth_level"],
        issued_by=row["issued_by"],
        issued_at=datetime.fromisoformat(row["issued_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        max_uses=row["max_uses"],
        used_count=row["used_count"],
        revoked_at=datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None,
    )


def create_approval(
    profile_id: str,
    scope: str,
    auth_level: int,
    issued_by: str,
    ttl_seconds: int = 3600,
    max_uses: int = 1,
) -> Approval:
    """
    Create a new approval artifact.
    No enforcement, just data creation.
    """
    profile_id = (profile_id or "").strip()
    scope = (scope or "").strip()
    issued_by = (issued_by or "").strip()
    if not profile_id or not scope or not issued_by:
        raise ValueError("profile_id, scope, and issued_by must be non-empty")

    issued_at = datetime.utcnow()
    expires_at = issued_at + timedelta(seconds=ttl_seconds)

    with _get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO approvals
            (profile_id, scope, auth_level, issued_by, issued_at, expires_at, max_uses, used_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            profile_id,
            scope,
            auth_level,
            issued_by,
            issued_at.isoformat(),
            expires_at.isoformat(),
            max_uses,
        ))
        approval_id = cur.lastrowid
        conn.commit()

    return Approval(
        id=approval_id,
        profile_id=profile_id,
        scope=scope,
        auth_level=auth_level,
        issued_by=issued_by,
        issued_at=issued_at,
        expires_at=expires_at,
        max_uses=max_uses,
        used_count=0,
        revoked_at=None,
    )


def get_approval(approval_id: int) -> Optional[Approval]:
    """
    Retrieve an approval by ID.
    Read-only, no consumption.
    """
    with _get_conn() as conn:
        cur = conn.execute("""
            SELECT * FROM approvals WHERE id = ?
        """, (approval_id,))
        row = cur.fetchone()
        return _row_to_approval(row) if row else None


def list_active_approvals(profile_id: str, limit: int = 50) -> List[Approval]:
    """
    List active approvals for a profile.
    Active: not expired, used_count < max_uses.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return []

    now = datetime.utcnow().isoformat()

    with _get_conn() as conn:
        cur = conn.execute("""
            SELECT * FROM approvals
            WHERE profile_id = ?
              AND expires_at > ?
              AND used_count < max_uses
              AND revoked_at IS NULL
            ORDER BY expires_at DESC
            LIMIT ?
        """, (profile_id, now, limit))
        rows = cur.fetchall()

    return [_row_to_approval(row) for row in rows]


def revoke_approval(approval_id: int, profile_id: str) -> bool:
    """
    Revoke an approval immediately.
    Only allows revocation if profile_id matches.
    Returns True if revoked, False if not found or mismatch.
    """
    revoked_at = datetime.utcnow().isoformat()

    with _get_conn() as conn:
        cur = conn.execute("""
            UPDATE approvals
            SET revoked_at = ?
            WHERE id = ? AND profile_id = ?
        """, (revoked_at, approval_id, profile_id))

        success = cur.rowcount > 0
        conn.commit()
        return success