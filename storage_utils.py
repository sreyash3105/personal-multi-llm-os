import json
import os
import shutil
from typing import Any, Callable, Optional


def atomic_write_text(path: str, data: str, make_backup: bool = True) -> None:
    """
    Safely write text data to a file:
    - Optionally create/overwrite a .bak backup of the existing file.
    - Write to a temporary file first.
    - Atomically replace the target file.
    """
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    if make_backup and os.path.exists(path):
        backup_path = f"{path}.bak"
        try:
            shutil.copy2(path, backup_path)
        except OSError:
            # Backup failure should not block the main write.
            pass

    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(data)

    # Atomic replace on most OSes.
    os.replace(tmp_path, path)


def load_json_with_backup(
    path: str,
    default_factory: Optional[Callable[[], Any]] = None,
) -> Any:
    """
    Load JSON from path; on failure, try .bak; on full failure, return default_factory() or {}.
    """
    if default_factory is None:
        default_factory = dict

    # Try main file
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        pass

    # Try backup
    backup_path = f"{path}.bak"
    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        pass

    # Fall back to default
    return default_factory()