# screen.capture Capability

## Contract

### Optional Fields
- `region` (tuple): (x, y, width, height) for partial capture

### Constraints
- Full-screen or explicit region only
- Resolution is capped (default: 3840x2160)
- Rate-limited (default: 1000ms minimum)
- No continuous capture
- No automatic saving
- No format conversion

### Consequence Level
LOW

### Friction
None (0 seconds)

## Refusals

| Refusal | Condition |
|---------|-----------|
| `REGION_INVALID` | Invalid region dimensions or coordinates |
| `RATE_LIMIT_EXCEEDED` | Capture rate exceeds limit |
| `UNSPECIFIED_REGION` | Region required when full-screen disabled |

## Configuration

```python
from backend.core.capabilities.screen_strict import ScreenConfig

config = ScreenConfig(
    max_width=3840,
    max_height=2160,
    min_rate_limit_ms=1000,  # 1 second
    allow_full_screen=True,
    forbid_continuous_capture=True,
)
```

## Example

```python
from backend.core.capabilities.screen_strict import ScreenCapture

result = ScreenCapture.execute({
    "region": (0, 0, 1920, 1080),
}, config)
```

## Non-Goals
- No continuous capture
- No automatic recording
- No format conversion
- No compression
- No video capture
- No mouse/keyboard input
