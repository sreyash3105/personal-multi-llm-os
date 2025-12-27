# process.spawn Capability

## Contract

### Required Fields
- `executable` (string): Path to executable
- `args` (list): Command-line arguments

### Optional Fields
- `timeout` (integer): Timeout in seconds (default: 30)
- `working_dir` (string): Working directory
- `capture_output` (boolean): Capture stdout/stderr (default: true)

### Constraints
- Executable must be in allowlist
- Shell invocation is FORBIDDEN
- Environment inheritance is disabled by default
- Timeout cannot exceed maximum
- Output size is capped
- No interactive processes

### Consequence Level
HIGH

### Friction
10 seconds (or more depending on confidence)

## Refusals

| Refusal | Condition |
|---------|-----------|
| `EXECUTABLE_NOT_ALLOWED` | Executable not in allowlist |
| `TIMEOUT_EXCEEDED` | Timeout exceeds limit |
| `OUTPUT_LIMIT_EXCEEDED` | Output size exceeds limit |
| `MISSING_EXECUTABLE` | Executable field missing |
| `MISSING_ARGS` | Args field missing |

## Configuration

```python
from backend.core.capabilities.process_strict import ProcessConfig

config = ProcessConfig(
    allowed_executables={"/usr/bin/python3", "python3"},
    max_timeout_seconds=60,
    max_output_bytes=10 * 1024 * 1024,  # 10MB
    forbid_shell=True,
    forbid_environment_inheritance=True,
)
```

## Example

```python
from backend.core.capabilities.process_strict import ProcessSpawn

result = ProcessSpawn.execute({
    "executable": "python3",
    "args": ["-c", "print('Hello')"],
    "timeout": 30,
}, config)
```

## Non-Goals
- No shell execution
- No environment variable injection
- No process tree management
- No process monitoring
- No stdin interaction
- No background processes
