"""
permission_manager.py (Phase C1)

Foundation for explicit permission system.
Manages permission grants, revocations, consumption, and audit logging.

NO ENFORCEMENT YET - this is storage and metadata only.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.config import HISTORY_DIR, PERMISSION_SYSTEM_ENABLED
from backend.modules.telemetry.history import history_logger

# Database path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PERMISSIONS_DB_PATH = DATA_DIR / "permissions.sqlite3"


def _get_conn() -> sqlite3.Connection:
    """Get SQLite connection with proper config."""
    conn = sqlite3.connect(str(PERMISSIONS_DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except sqlite3.DatabaseError:
        pass
    return conn


def _init_db() -> None:
    """Initialize permissions database schema."""
    with _get_conn() as conn:
        # Permissions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                auth_level_min INTEGER NOT NULL,
                granted_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_count INTEGER NOT NULL DEFAULT 0,
                max_uses INTEGER NOT NULL DEFAULT 1,
                metadata TEXT,
                reason TEXT,
                revoked_at TEXT
            )
        """)

        # Permission usage log
        conn.execute("""
            CREATE TABLE IF NOT EXISTS permission_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_id INTEGER NOT NULL,
                used_at TEXT NOT NULL,
                operation TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                output_summary TEXT,
                FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE
            )
        """)

        # Indexes
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_permissions_profile_active
            ON permissions (profile_id, revoked_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_permissions_expires_at
            ON permissions (expires_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_permission_time
            ON permission_usage_log (permission_id, used_at)
        """)

        conn.commit()


# Initialize on import
_init_db()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert SQLite row to dict."""
    return {
        "id": row["id"],
        "profile_id": row["profile_id"],
        "scope": row["scope"],
        "auth_level_min": row["auth_level_min"],
        "granted_at": row["granted_at"],
        "expires_at": row["expires_at"],
        "used_count": row["used_count"],
        "max_uses": row["max_uses"],
        "metadata": row["metadata"],
        "reason": row["reason"],
        "revoked_at": row["revoked_at"],
    }


def _now() -> str:
    """Current timestamp as ISO string."""
    return datetime.utcnow().isoformat(timespec="seconds")


def grant_permission(
    *,
    profile_id: str,
    scope: str,
    auth_level_min: int = 3,
    ttl_seconds: int = 3600,
    max_uses: int = 1,
    reason: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new permission grant.

    Returns the created permission dict.
    """
    profile_id = (profile_id or "").strip()
    scope = (scope or "").strip()
    if not profile_id or not scope:
        raise ValueError("profile_id and scope must be non-empty")

    granted_at = _now()
    expires_at = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")

    metadata_json = None
    if metadata:
        import json
        metadata_json = json.dumps(metadata)

    # Check for existing active permission for same scope
    with _get_conn() as conn:
        cur = conn.execute("""
            INSERT OR REPLACE INTO permissions
            (profile_id, scope, auth_level_min, granted_at, expires_at, used_count, max_uses, metadata, reason, revoked_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, NULL)
            RETURNING id, profile_id, scope, auth_level_min, granted_at, expires_at, used_count, max_uses, metadata, reason, revoked_at
        """, (profile_id, scope, auth_level_min, granted_at, expires_at, max_uses, metadata_json, reason))

        row = cur.fetchone()
        if not row:
            raise RuntimeError("Failed to create permission")

        permission_id = row["id"]
        conn.commit()

        # Log to history
        try:
            history_logger.log({
                "kind": "permission_granted",
                "permission_id": permission_id,
                "profile_id": profile_id,
                "scope": scope,
                "auth_level_min": auth_level_min,
                "ttl_seconds": ttl_seconds,
                "max_uses": max_uses,
                "reason": reason,
            })
        except Exception:
            pass

    return _row_to_dict(row) if row else {}


def revoke_permission(
    *,
    profile_id: str,
    permission_id: int,
    revoked_reason: str = "",
) -> bool:
    """
    Revoke a permission immediately.

    Returns True if revoked, False if not found or already revoked.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return False

    revoked_at = _now()

    with _get_conn() as conn:
        cur = conn.execute("""
            UPDATE permissions
            SET revoked_at = ?
            WHERE id = ? AND profile_id = ? AND revoked_at IS NULL
        """, (revoked_at, permission_id, profile_id))

        success = cur.rowcount > 0
        conn.commit()

        if success:
            # Log revocation
            try:
                history_logger.log({
                    "kind": "permission_revoked",
                    "permission_id": permission_id,
                    "profile_id": profile_id,
                    "revoked_reason": revoked_reason,
                })
            except Exception:
                pass

    return success


def check_permission(
    *,
    profile_id: str,
    scope: str,
    auth_level_min: int,
    consume: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Check if a valid permission exists.

    If consume=True, atomically consume one use.
    Returns permission dict if valid, None otherwise.
    """
    profile_id = (profile_id or "").strip()
    scope = (scope or "").strip()
    if not profile_id or not scope:
        return None

    now = _now()

    with _get_conn() as conn:
        if consume:
            # Atomic consume
            cur = conn.execute("""
                UPDATE permissions
                SET used_count = used_count + 1
                WHERE profile_id = ?
                  AND scope = ?
                  AND auth_level_min <= ?
                  AND revoked_at IS NULL
                  AND expires_at > ?
                  AND used_count < max_uses
                RETURNING *
            """, (profile_id, scope, auth_level_min, now))
        else:
            # Just check
            cur = conn.execute("""
                SELECT * FROM permissions
                WHERE profile_id = ?
                  AND scope = ?
                  AND auth_level_min <= ?
                  AND revoked_at IS NULL
                  AND expires_at > ?
                  AND used_count < max_uses
                LIMIT 1
            """, (profile_id, scope, auth_level_min, now))

        row = cur.fetchone()
        if not row:
            return None

        permission = _row_to_dict(row)
        if consume:
            # Insert usage log
            conn.execute("""
                INSERT INTO permission_usage_log
                (permission_id, used_at, operation, success, output_summary)
                VALUES (?, ?, ?, ?, ?)
            """, (permission["id"], _now(), "consume", True, f"Remaining: {permission['max_uses'] - permission['used_count']}"))

            # Log to history
            try:
                history_logger.log({
                    "kind": "permission_consumed",
                    "permission_id": permission["id"],
                    "profile_id": profile_id,
                    "scope": scope,
                    "operation": "consume_permission",
                    "remaining_uses": permission["max_uses"] - permission["used_count"],
                })
            except Exception:
                pass

        conn.commit()
        return permission


def consume_permission(
    *,
    profile_id: str,
    scope: str,
    auth_level_min: int,
    operation: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Consume one use of a permission.

    Equivalent to check_permission(consume=True).
    """
    return check_permission(
        profile_id=profile_id,
        scope=scope,
        auth_level_min=auth_level_min,
        consume=True,
    )


def get_active_permissions(
    *,
    profile_id: str,
    include_expired: bool = False,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Get active permissions for a profile.
    """
    profile_id = (profile_id or "").strip()
    if not profile_id:
        return []

    now = _now()

    with _get_conn() as conn:
        if include_expired:
            cur = conn.execute("""
                SELECT * FROM permissions
                WHERE profile_id = ?
                ORDER BY expires_at DESC
                LIMIT ?
            """, (profile_id, limit))
        else:
            cur = conn.execute("""
                SELECT * FROM permissions
                WHERE profile_id = ?
                  AND revoked_at IS NULL
                  AND expires_at > ?
                  AND used_count < max_uses
                ORDER BY expires_at ASC
                LIMIT ?
            """, (profile_id, now, limit))

        rows = cur.fetchall()

    return [_row_to_dict(row) for row in rows]


def get_permission_usage_log(
    *,
    permission_id: int,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Get usage log for a permission.
    """
    with _get_conn() as conn:
        cur = conn.execute("""
            SELECT * FROM permission_usage_log
            WHERE permission_id = ?
            ORDER BY used_at DESC
            LIMIT ?
        """, (permission_id, limit))

        rows = cur.fetchall()

    return [
        {
            "id": row["id"],
            "permission_id": row["permission_id"],
            "used_at": row["used_at"],
            "operation": row["operation"],
            "success": bool(row["success"]),
            "output_summary": row["output_summary"],
        }
        for row in rows
    ]


def cleanup_expired_permissions(max_age_seconds: int = 86400) -> int:
    """
    Clean up expired and fully used permissions older than max_age_seconds.

    Returns number of permissions deleted.
    """
    cutoff = (datetime.utcnow() - timedelta(seconds=max_age_seconds)).isoformat(timespec="seconds")

    with _get_conn() as conn:
        cur = conn.execute("""
            DELETE FROM permissions
            WHERE revoked_at IS NOT NULL
               OR (expires_at < ? AND used_count >= max_uses)
        """, (cutoff,))

        deleted = cur.rowcount
        conn.commit()

        if deleted > 0:
            try:
                history_logger.log({
                    "kind": "permission_cleanup",
                    "deleted_count": deleted,
                    "cutoff_time": cutoff,
                })
            except Exception:
                pass

    return deleted


def check_permission_for_tool_execution(
    *,
    profile_id: str,
    tool_name: str,
    scope: str,
    required_auth_level: int,
) -> Optional[Dict[str, Any]]:
    """
    Hook for permission checking during tool execution.

    This is a no-op when PERMISSION_SYSTEM_ENABLED is False.
    When enabled, it will check for valid permissions.

    Returns permission data if valid, None otherwise.
    """
    if not PERMISSION_SYSTEM_ENABLED:
        return None  # No enforcement

    # Future: implement permission checking logic
    # For now, placeholder
    return check_permission(
        profile_id=profile_id,
        scope=scope,
        auth_level_min=required_auth_level,
        consume=True,
    )


def get_permission_stats(profile_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get read-only statistics about permissions.
    """
    with _get_conn() as conn:
        if profile_id:
            # Stats for specific profile
            cur = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN revoked_at IS NULL AND expires_at > ? AND used_count < max_uses THEN 1 END) as active,
                    COUNT(CASE WHEN revoked_at IS NOT NULL THEN 1 END) as revoked,
                    COUNT(CASE WHEN expires_at <= ? THEN 1 END) as expired,
                    SUM(used_count) as total_uses
                FROM permissions
                WHERE profile_id = ?
            """, (_now(), _now(), profile_id))
        else:
            # Global stats
            cur = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN revoked_at IS NULL AND expires_at > ? AND used_count < max_uses THEN 1 END) as active,
                    COUNT(CASE WHEN revoked_at IS NOT NULL THEN 1 END) as revoked,
                    COUNT(CASE WHEN expires_at <= ? THEN 1 END) as expired,
                    SUM(used_count) as total_uses
                FROM permissions
            """, (_now(), _now()))

        row = cur.fetchone()

    return {
        "total_permissions": row["total"] or 0,
        "active_permissions": row["active"] or 0,
        "revoked_permissions": row["revoked"] or 0,
        "expired_permissions": row["expired"] or 0,
        "total_uses": row["total_uses"] or 0,
    }