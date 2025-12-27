"""
PatternRecord Persistence Model

AIOS Next Frontier - Pattern Aggregation Layer

SQLite persistence for pattern events.
Append-only - no deletion, no modification.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.pattern_event import PatternEvent, PatternType, PatternSeverity


# Database location
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PATTERNS_DB_PATH = DATA_DIR / "patterns.sqlite3"


def _get_conn() -> sqlite3.Connection:
    """
    Get SQLite connection with hardened config.

    Configuration:
        - WAL journal mode for durability
        - Synchronous = NORMAL for performance/safety balance
        - Row factory for dict-like access
    """
    conn = sqlite3.connect(PATTERNS_DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except sqlite3.DatabaseError:
        pass
    return conn


def _init_db() -> None:
    """
    Initialize patterns database schema.

    Table is APPEND-ONLY.
    No UPDATE, no DELETE allowed.
    """
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pattern_events (
                pattern_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                pattern_severity TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                profile_id TEXT NOT NULL,
                session_id TEXT,
                triggering_action TEXT NOT NULL,
                pattern_details TEXT NOT NULL,
                related_failure_id TEXT,
                related_action_id TEXT
            )
            """
        )

        # Indexes for query performance
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_patterns_profile
            ON pattern_events (profile_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_patterns_type
            ON pattern_events (pattern_type)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_patterns_timestamp
            ON pattern_events (timestamp DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_patterns_profile_type
            ON pattern_events (profile_id, pattern_type)
            """
        )

        conn.commit()


# Initialize schema at import time
_init_db()


class PatternRecord:
    """
    Pattern event persistence manager.

    Append-only storage.
    No deletion.
    No modification.
    """

    @staticmethod
    def insert(pattern_event: PatternEvent) -> None:
        """
        Insert pattern event into database.

        NO validation beyond schema.
        NO transformation.
        APPEND-ONLY.
        """
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO pattern_events (
                    pattern_id, pattern_type, pattern_severity, timestamp,
                    profile_id, session_id, triggering_action, pattern_details,
                    related_failure_id, related_action_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pattern_event.pattern_id,
                    pattern_event.pattern_type.value,
                    pattern_event.pattern_severity.value,
                    pattern_event.timestamp,
                    pattern_event.context_snapshot["profile_id"],
                    pattern_event.context_snapshot.get("session_id"),
                    pattern_event.context_snapshot["triggering_action"],
                    str(pattern_event.context_snapshot["pattern_details"]),
                    pattern_event.related_failure_id,
                    pattern_event.related_action_id,
                ),
            )
            conn.commit()

    @staticmethod
    def query_by_profile(
        profile_id: str,
        pattern_type: Optional[PatternType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query pattern events for a specific profile.

        READ-ONLY.
        NO modification.
        """
        query = "SELECT * FROM pattern_events WHERE profile_id = ?"
        params: List[Any] = [profile_id]

        if pattern_type is not None:
            query += " AND pattern_type = ?"
            params.append(pattern_type.value)

        if start_time is not None:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time is not None:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with _get_conn() as conn:
            cur = conn.execute(query, params)
            rows = cur.fetchall()

        return [
            {
                "pattern_id": row["pattern_id"],
                "pattern_type": row["pattern_type"],
                "pattern_severity": row["pattern_severity"],
                "timestamp": row["timestamp"],
                "profile_id": row["profile_id"],
                "session_id": row["session_id"],
                "triggering_action": row["triggering_action"],
                "pattern_details": eval(row["pattern_details"]),  # Stored as JSON string
                "related_failure_id": row["related_failure_id"],
                "related_action_id": row["related_action_id"],
            }
            for row in rows
        ]

    @staticmethod
    def count_by_type(
        pattern_type: PatternType,
        profile_id: Optional[str] = None,
        time_window: Optional[timedelta] = None,
    ) -> int:
        """
        Count pattern occurrences.

        READ-ONLY.
        NO modification.
        """
        query = "SELECT COUNT(*) as count FROM pattern_events WHERE pattern_type = ?"
        params: List[Any] = [pattern_type.value]

        if profile_id is not None:
            query += " AND profile_id = ?"
            params.append(profile_id)

        if time_window is not None:
            cutoff = (datetime.utcnow() - time_window).isoformat()
            query += " AND timestamp >= ?"
            params.append(cutoff)

        with _get_conn() as conn:
            cur = conn.execute(query, params)
            row = cur.fetchone()

        return int(row["count"] or 0)

    @staticmethod
    def get_last_occurrence(
        pattern_type: PatternType,
        profile_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get most recent pattern occurrence.

        READ-ONLY.
        NO modification.
        """
        query = "SELECT * FROM pattern_events WHERE pattern_type = ?"
        params: List[Any] = [pattern_type.value]

        if profile_id is not None:
            query += " AND profile_id = ?"
            params.append(profile_id)

        query += " ORDER BY timestamp DESC LIMIT 1"

        with _get_conn() as conn:
            cur = conn.execute(query, params)
            row = cur.fetchone()

        if not row:
            return None

        return {
            "pattern_id": row["pattern_id"],
            "pattern_type": row["pattern_type"],
            "pattern_severity": row["pattern_severity"],
            "timestamp": row["timestamp"],
            "profile_id": row["profile_id"],
            "session_id": row["session_id"],
            "triggering_action": row["triggering_action"],
            "pattern_details": eval(row["pattern_details"]),
            "related_failure_id": row["related_failure_id"],
            "related_action_id": row["related_action_id"],
        }

    @staticmethod
    def get_statistics(
        profile_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get pattern statistics.

        READ-ONLY aggregation.
        NO modification.
        """
        query = """
            SELECT
                pattern_type,
                COUNT(*) as count,
                MIN(timestamp) as first_seen,
                MAX(timestamp) as last_seen
            FROM pattern_events
        """

        params: List[Any] = []

        if profile_id is not None:
            query += " WHERE profile_id = ?"
            params.append(profile_id)

        query += " GROUP BY pattern_type ORDER BY count DESC"

        with _get_conn() as conn:
            cur = conn.execute(query, params)
            rows = cur.fetchall()

        return [
            {
                "pattern_type": row["pattern_type"],
                "count": int(row["count"]),
                "first_seen": row["first_seen"],
                "last_seen": row["last_seen"],
            }
            for row in rows
        ]


# NO UPDATE, NO DELETE, NO PURGE methods intentionally omitted.
# Append-only persistence is enforced by interface only.
