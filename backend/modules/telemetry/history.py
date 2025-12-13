# backend/modules/telemetry/history.py
"""
Rotating history logger.

REWRITTEN FOR STABILITY:
- Forces absolute paths for database location.
- Prints explicit errors to stderr on failure.
- Maintains dual-write (SQLite + JSONL) integrity.
- FIX: log() accepts kwargs to support calls from stt_service.
"""

import json
import threading
import sys
import traceback
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.core.config import HISTORY_DIR, HISTORY_MAX_ENTRIES

# --- 1. Force Absolute Paths ---
# resolving: backend/modules/telemetry/history.py -> ... -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
HISTORY_DIR_PATH = (BASE_DIR / HISTORY_DIR).resolve()
HISTORY_DIR_PATH.mkdir(parents=True, exist_ok=True)

DB_PATH = HISTORY_DIR_PATH / "history.sqlite3"

# Print startup info so we know exactly where data is going
print(f"[HISTORY] Initializing Logger...")
print(f"[HISTORY] JSONL Dir:  {HISTORY_DIR_PATH}")
print(f"[HISTORY] SQLite DB:  {DB_PATH}")


# --- 2. Database Connection & Schema ---

def _get_conn() -> sqlite3.Connection:
    """Open a robust SQLite connection with WAL mode."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except sqlite3.DatabaseError as e:
        print(f"[HISTORY] Warning: PRAGMA failed: {e}", file=sys.stderr)
    return conn

def _init_db() -> None:
    """Ensure the history table exists."""
    try:
        with _get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history_records (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts TEXT NOT NULL,
                  data_json TEXT NOT NULL
                );
                """
            )
            # Index for faster dashboard sorting
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_ts_id ON history_records(ts, id);"
            )
            conn.commit()
    except Exception as e:
        print(f"[HISTORY] FATAL: Could not init DB at {DB_PATH}", file=sys.stderr)
        traceback.print_exc()

# Initialize on import
_init_db()


# --- 3. The Logger Class ---

class HistoryLogger:
    def __init__(self, directory: Path, max_entries: int):
        self._dir = directory
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._entries_in_current = 0
        self._file_index = 1
        self._current_path: Path
        self._open_new_file()

    def _open_new_file(self) -> None:
        """Rotate to a new JSONL file."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_path = self._dir / f"history_{ts}_{self._file_index:03d}.jsonl"
        self._entries_in_current = 0
        self._file_index += 1

    def _write_jsonl(self, entry: Dict[str, Any]) -> None:
        """Backup write to text file."""
        if self._entries_in_current >= self._max_entries:
            self._open_new_file()
        try:
            with self._current_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._entries_in_current += 1
        except Exception as e:
            print(f"[HISTORY] JSONL Write Error: {e}", file=sys.stderr)

    def _write_sqlite(self, entry: Dict[str, Any]) -> None:
        """Primary write to SQLite."""
        try:
            data_json = json.dumps(entry, ensure_ascii=False)
            with _get_conn() as conn:
                conn.execute(
                    "INSERT INTO history_records (ts, data_json) VALUES (?, ?);",
                    (entry.get("ts"), data_json),
                )
                conn.commit()
        except Exception as e:
            print(f"[HISTORY] SQLite Write Error: {e}", file=sys.stderr)

    def log(self, record: Optional[Dict[str, Any]] = None, **kwargs) -> None:
        """
        Public API: Log a record (thread-safe).
        
        Now flexible! Can be called in two ways:
        1. history_logger.log({"mode": "stt", "text": "..."})
        2. history_logger.log(mode="stt", payload={...})  <-- Used by STT Service
        """
        try:
            with self._lock:
                # 1. Normalize input into a single dictionary
                data = record.copy() if record else {}
                data.update(kwargs)

                # 2. Add timestamp if missing
                if "ts" not in data:
                    data["ts"] = datetime.now().isoformat()
                
                # 3. Write to both storages
                self._write_jsonl(data)
                self._write_sqlite(data)
        except Exception as e:
            print(f"[HISTORY] Log Failure: {e}", file=sys.stderr)


# --- 4. Read API (for Dashboard) ---

def load_recent_records(limit: int = 50) -> List[Dict[str, Any]]:
    """Read recently logged records from SQLite."""
    try:
        with _get_conn() as conn:
            cur = conn.execute(
                """
                SELECT data_json FROM history_records
                ORDER BY ts DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()
            
        results = []
        for row in rows:
            try:
                results.append(json.loads(row["data_json"]))
            except json.JSONDecodeError:
                continue
        return results 
    except Exception as e:
        print(f"[HISTORY] Read Error: {e}", file=sys.stderr)
        return []

# Global instance
history_logger = HistoryLogger(HISTORY_DIR_PATH, HISTORY_MAX_ENTRIES)