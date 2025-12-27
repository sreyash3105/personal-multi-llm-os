# filesystem.write Capability

## Contract

### Required Fields
- `path` (string): Absolute path to file
- `content` (string): Content to write

### Constraints
- Path must be absolute
- Path must not be a symlink
- Path must be within allowed directories (if configured)
- Content size must not exceed limit
- Parent directories are created automatically
- Existing directories cannot be overwritten

### Consequence Level
HIGH

### Friction
10 seconds (or more depending on confidence)

## Refusals

| Refusal | Condition |
|---------|-----------|
| `PATH_NOT_EXPLICIT` | Path is empty or not absolute |
| `PATH_OUT_OF_SCOPE` | Path outside allowed directories |
| `FILE_TOO_LARGE` | Content size exceeds limit |
| `TYPE_NOT_ALLOWED` | Failed to write file |
| `PATH_IS_SYMLINK` | Symlinks are forbidden |
| `IS_DIRECTORY` | Path is a directory |

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
from backend.core.capabilities.filesystem_strict import FilesystemWrite

result = FilesystemWrite.execute({
    "path": "/safe/data/file.txt",
    "content": "Hello, world!",
}, config)
```

## Non-Goals
- No appending to files (only overwrite)
- No atomic writes
- No file locking
- No file watching
- No content validation
