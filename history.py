# history.py
"""
Rotating history logger + helpers to read recent interactions.

HARDNING BASE:
- Writes history to BOTH:
  - JSONL files in HISTORY_DIR/history_*.jsonl  (for backup / inspection)
  - SQLite DB in HISTORY_DIR/history.sqlite3   (for fast querying)
- load_recent_records() now reads ONLY from SQLite.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import sqlite3

from config import HISTORY_DIR, HISTORY_MAX_ENTRIES


# =========================
# Paths
# =========================

HISTORY_DIR_PATH = Path(HISTORY_DIR)
HISTORY_DIR_PATH.mkdir(parents=True, exist_ok=True)

DB_PATH = HISTORY_DIR_PATH / "history.sqlite3"


# =========================
# SQLite backing store
# =========================

def _get_conn() -> sqlite3.Connection:
    """
    Open a SQLite connection for history storage.
    - WAL journaling + NORMAL sync for durability/performance
    - 30s timeout to avoid database-locked crashes
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except sqlite3.DatabaseError:
        # If PRAGMAs fail, don't break logging.
        pass
    return conn


def _init_db() -> None:
    """Ensure the history SQLite table exists."""
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history_records (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT NOT NULL,          -- ISO timestamp
              data_json TEXT NOT NULL    -- full record as JSON (including ts)
            );
            """
        )
        conn.commit()


# Initialize SQLite store on import
_init_db()


# =========================
# JSONL rotating logger (legacy + backup)
# =========================

class HistoryLogger:
    """
    Thread-safe history logger.

    - Primary read path: SQLite (see load_recent_records).
    - Write path: JSONL + SQLite mirroring.
    """

    def __init__(self, directory: str, max_entries: int):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)

        self._max_entries = max_entries
        self._lock = threading.Lock()

        self._entries_in_current = 0
        self._file_index = 1
        self._current_path: Path
        self._open_new_file()

    def _open_new_file(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_path = self._dir / f"history_{ts}_{self._file_index:03d}.jsonl"
        self._entries_in_current = 0
        self._file_index += 1

    def _write_jsonl(self, entry: Dict[str, Any]) -> None:
        """
        Append entry to the current JSONL file, handling rotation.
        This is kept for backup / manual inspection, not for primary reads.
        """
        if self._entries_in_current >= self._max_entries:
            self._open_new_file()

        with self._current_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._entries_in_current += 1

    def _write_sqlite(self, entry: Dict[str, Any]) -> None:
        """
        Mirror the entry into SQLite (primary source for reading).
        Best-effort only: any error here must not affect the caller.
        """
        try:
            data_json = json.dumps(entry, ensure_ascii=False)
        except Exception:
            return

        try:
            with _get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO history_records (ts, data_json)
                    VALUES (?, ?);
                    """,
                    (entry.get("ts") or datetime.now().isoformat(), data_json),
                )
                conn.commit()
        except Exception:
            # History DB must never break the app.
            pass

    def log(self, record: Dict[str, Any]) -> None:
        """
        Append a single JSON record to history.

        - Adds an ISO `ts` automatically.
        - Writes to JSONL (legacy/backup).
        - Mirrors to SQLite (used by load_recent_records and dashboard).
        - Never raises exceptions.
        """
        try:
            with self._lock:
                entry = {"ts": datetime.now().isoformat(), **record}

                # JSONL: keep legacy log files around
                try:
                    self._write_jsonl(entry)
                except Exception:
                    pass

                # SQLite: primary read path
                try:
                    self._write_sqlite(entry)
                except Exception:
                    pass

        except Exception:
            # Logging is best-effort only.
            pass


# =========================
# Load recent records (now from SQLite)
# =========================

def load_recent_records(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Load up to `limit` most recent records from the SQLite history table.

    Returns:
        List of dicts (oldest -> newest), same shape as the JSON records used
        previously by the dashboard and pipeline.

    If anything goes wrong with SQLite, falls back to [].
    """
    try:
        with _get_conn() as conn:
            cur = conn.execute(
                """
                SELECT data_json
                FROM history_records
                ORDER BY ts DESC, id DESC
                LIMIT ?
                """,
                (int(limit),),
            )
            rows = cur.fetchall()
    except Exception:
        return []

    records: List[Dict[str, Any]] = []
    for row in rows:
        raw = row["data_json"]
        if raw is None:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        records.append(rec)

    # rows were fetched newest -> oldest; reverse to oldest -> newest
    records.reverse()
    return records


# Global logger instance used by the server
history_logger = HistoryLogger(HISTORY_DIR, HISTORY_MAX_ENTRIES)
