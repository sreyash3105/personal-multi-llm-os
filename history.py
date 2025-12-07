# history.py
"""
Rotating history logger + helpers to read recent interactions.

Each interaction is appended as JSON_LINES into history/history_*.jsonl.
When a file reaches HISTORY_MAX_ENTRIES, a new one is auto-created.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from config import HISTORY_DIR, HISTORY_MAX_ENTRIES


class HistoryLogger:
    def __init__(self, directory: str, max_entries: int):
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._entries_in_current = 0
        self._file_index = 1
        self._open_new_file()

    def _open_new_file(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_path = self._dir / f"history_{ts}_{self._file_index:03d}.jsonl"
        self._entries_in_current = 0
        self._file_index += 1

    def log(self, record: Dict[str, Any]):
        """
        Append a single JSON record to the current history file.
        Never raises exceptions (logging must not crash the app).
        """
        try:
            with self._lock:
                if self._entries_in_current >= self._max_entries:
                    self._open_new_file()

                entry = {"ts": datetime.now().isoformat(), **record}
                with self._current_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

                self._entries_in_current += 1
        except Exception:
            # history must never break the main flow
            pass


def load_recent_records(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Traverse history files (newest first) and return up to `limit`
    most recent records, ordered from oldest -> newest.

    Used by the pipeline when context is requested (///ctx, ///continue).
    """
    dir_path = Path(HISTORY_DIR)
    if not dir_path.exists():
        return []

    files = sorted(dir_path.glob("history_*.jsonl"), reverse=True)
    collected: List[Dict[str, Any]] = []

    for fp in files:
        try:
            with fp.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            continue

        # read from bottom upwards (newest entries first in this file)
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue

            collected.append(rec)
            if len(collected) >= limit:
                return list(reversed(collected))

    return list(reversed(collected))


# Global logger instance used by the server
history_logger = HistoryLogger(HISTORY_DIR, HISTORY_MAX_ENTRIES)
