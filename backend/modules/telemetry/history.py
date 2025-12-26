# backend/modules/telemetry/history.py
"""
Rotating history logger.

REWRITTEN FOR STABILITY:
- Forces absolute paths for database location.
- Prints explicit errors to stderr on failure.
- Maintains dual-write (SQLite + JSONL) integrity.
- FIX: log() accepts kwargs to support calls from stt_service.
- FIX: Explicit connection closing to prevent file handle leaks.
"""

import json
import threading
import sys
import traceback
import sqlite3
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.core.config import HISTORY_DIR, HISTORY_MAX_ENTRIES

logger = logging.getLogger(__name__)

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

# Connection pool for better resource management
_connection_lock = threading.Lock()
_connection_pool: List[sqlite3.Connection] = []

def _get_conn() -> sqlite3.Connection:
    """
    Get a database connection with proper configuration and pooling.

    Uses connection pooling to reduce overhead and improve stability.
    """
    start_time = time.time()

    with _connection_lock:
        # Try to reuse an existing connection
        if _connection_pool:
            conn = _connection_pool.pop()
            try:
                # Test connection is still valid
                conn.execute("SELECT 1").fetchone()
                conn_time = time.time() - start_time
                if conn_time > 0.1:  # Log slow connections
                    logger.warning(f"Slow connection acquisition: {conn_time:.3f}s")
                return conn
            except sqlite3.Error:
                # Connection is dead, create new one
                try:
                    conn.close()
                except:
                    pass

        # Create new connection
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
            conn.row_factory = sqlite3.Row

            # Configure connection
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA temp_store = MEMORY;")
            conn.execute("PRAGMA cache_size = -2000;")  # 2MB cache

            conn_time = time.time() - start_time
            if conn_time > 0.1:  # Log slow connections
                logger.warning(f"Slow connection creation: {conn_time:.3f}s")

            return conn
        except sqlite3.DatabaseError as e:
            logger.error(f"Failed to create database connection: {e}")
            raise

def _return_conn(conn: sqlite3.Connection) -> None:
    """Return a connection to the pool for reuse."""
    with _connection_lock:
        if len(_connection_pool) < 5:  # Limit pool size
            try:
                # Test connection before returning to pool
                conn.execute("SELECT 1").fetchone()
                _connection_pool.append(conn)
            except sqlite3.Error:
                # Connection is bad, don't reuse
                try:
                    conn.close()
                except:
                    pass
        else:
            # Pool is full, close connection
            try:
                conn.close()
            except:
                pass

def _close_all_connections() -> None:
    """Close all connections in the pool (for shutdown)."""
    with _connection_lock:
        for conn in _connection_pool:
            try:
                conn.close()
            except:
                pass
        _connection_pool.clear()

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
        """Primary write to SQLite with proper transaction handling."""
        conn = None
        try:
            data_json = json.dumps(entry, ensure_ascii=False)
            conn = _get_conn()
            with conn:  # Transaction context manager
                conn.execute(
                    "INSERT INTO history_records (ts, data_json) VALUES (?, ?);",
                    (entry.get("ts"), data_json),
                )
        except Exception as e:
            logger.error(f"SQLite write error: {e}")
        finally:
            if conn:
                _return_conn(conn)

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
    conn = None
    try:
        conn = _get_conn()
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
            except json.JSONDecodeError as e:
                logger.warning(f"Skipping corrupted history record: {e}")
                continue
        return results
    except Exception as e:
        logger.error(f"History read error: {e}")
        return []
    finally:
        if conn:
            _return_conn(conn)

# --- 5. Health Monitoring ---

def get_health_status() -> Dict[str, Any]:
    """
    Return health status and metrics for monitoring.

    Useful for dashboards and alerting.
    """
    status = {
        "healthy": True,
        "database_path": str(DB_PATH),
        "jsonl_directory": str(HISTORY_DIR_PATH),
        "connection_pool_size": len(_connection_pool),
        "errors": []
    }

    try:
        # Test database connectivity
        conn = _get_conn()
        try:
            cur = conn.execute("SELECT COUNT(*) as count FROM history_records")
            row = cur.fetchone()
            status["record_count"] = row["count"]
        finally:
            _return_conn(conn)
    except Exception as e:
        status["healthy"] = False
        status["errors"].append(f"Database connectivity failed: {e}")

    try:
        # Check JSONL directory
        if not HISTORY_DIR_PATH.exists():
            status["healthy"] = False
            status["errors"].append("JSONL directory does not exist")
        else:
            jsonl_files = list(HISTORY_DIR_PATH.glob("*.jsonl"))
            status["jsonl_file_count"] = len(jsonl_files)
    except Exception as e:
        status["healthy"] = False
        status["errors"].append(f"JSONL directory check failed: {e}")

    return status

def get_performance_metrics() -> Dict[str, Any]:
    """
    Return performance metrics for monitoring.
    """
    metrics: Dict[str, Any] = {
        "connection_pool_size": len(_connection_pool),
        "max_pool_size": 5,
    }

    try:
        conn = _get_conn()
        try:
            # Get database file size
            db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
            metrics["database_size_bytes"] = db_size

            # Get record count
            cur = conn.execute("SELECT COUNT(*) as count FROM history_records")
            metrics["total_records"] = cur.fetchone()["count"]

            # Get latest record timestamp
            cur = conn.execute("SELECT ts FROM history_records ORDER BY ts DESC LIMIT 1")
            row = cur.fetchone()
            metrics["latest_record_ts"] = row["ts"] if row else None

        finally:
            _return_conn(conn)
    except Exception as e:
        metrics["error"] = str(e)

    return metrics

# Global instance
history_logger = HistoryLogger(HISTORY_DIR_PATH, HISTORY_MAX_ENTRIES)

# Register cleanup on exit
import atexit
atexit.register(_close_all_connections)