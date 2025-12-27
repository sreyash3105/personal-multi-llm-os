# filesystem.delete Capability

## Contract

### Required Fields
- `path` (string): Absolute path to file

### Constraints
- Path must be absolute
- Path must not be a symlink
- Path must be within allowed directories (if configured)
- Recursive deletion (directories) is FORBIDDEN
- Non-existent files return success with `deleted: false`

### Consequence Level
HIGH

### Friction
10 seconds (or more depending on confidence)

## Refusals

| Refusal | Condition |
|---------|-----------|
| `PATH_NOT_EXPLICIT` | Path is empty or not absolute |
| `PATH_OUT_OF_SCOPE` | Path outside allowed directories |
| `TYPE_NOT_ALLOWED` | Failed to delete file |
| `PATH_IS_SYMLINK` | Symlinks are forbidden |
| `IS_DIRECTORY` | Recursive delete forbidden |

## Configuration

```python
from backend.core.capabilities.filesystem_strict import FilesystemConfig

config = FilesystemConfig(
    allowed_directories={"/safe/path"},
    forbid_symlinks=True,
)
```

## Example

```python
from backend.core.capabilities.filesystem_strict import FilesystemDelete

result = FilesystemDelete.execute({
    "path": "/safe/data/file.txt",
}, config)
```

## Non-Goals
- No recursive deletion
- No wildcard deletion
- No directory deletion
- No trash/restore
- No undo
