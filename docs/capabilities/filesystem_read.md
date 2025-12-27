# filesystem.read Capability

## Contract

### Required Fields
- `path` (string): Absolute path to file

### Constraints
- Path must be absolute
- Path must not be a symlink
- Path must be within allowed directories (if configured)
- File must exist
- Path must not be a directory
- File size must not exceed limit (default: 10MB)

### Consequence Level
LOW

### Friction
None (0 seconds)

## Refusals

| Refusal | Condition |
|---------|-----------|
| `PATH_NOT_EXPLICIT` | Path is empty or not absolute |
| `PATH_OUT_OF_SCOPE` | Path outside allowed directories |
| `FILE_TOO_LARGE` | File size exceeds limit |
| `TYPE_NOT_ALLOWED` | Failed to read file type |
| `PATH_IS_SYMLINK` | Symlinks are forbidden |
| `IS_DIRECTORY` | Path is a directory, not a file |
| `FILE_NOT_FOUND` | File does not exist |

## Configuration

```python
from backend.core.capabilities.filesystem_strict import FilesystemConfig

config = FilesystemConfig(
    max_file_size=10 * 1024 * 1024,  # 10MB
    allowed_directories={"/safe/path"},
    forbid_symlinks=True,
)
```

## Example

```python
from backend.core.capabilities.filesystem_strict import FilesystemRead

result = FilesystemRead.execute({
    "path": "/safe/data/file.txt",
}, config)
```

## Non-Goals
- No globbing or pattern matching
- No directory listing
- No recursive operations
- No implicit path resolution
- No file watching
