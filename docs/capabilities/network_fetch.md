# network.fetch Capability

## Contract

### Required Fields
- `url` (string): HTTPS URL to fetch
- `method` (string): HTTP method (GET or POST)

### Optional Fields
- `headers` (dict): HTTP headers (cookies filtered)
- `body` (string): Request body (POST only)
- `timeout` (integer): Timeout in seconds (default: 30)

### Constraints
- HTTPS only
- Explicit domain allowlist
- Methods: GET or POST only
- Payload size capped
- No cookies
- No redirects
- SSL verification enforced

### Consequence Level
MEDIUM

### Friction
3 seconds (or more depending on confidence)

## Refusals

| Refusal | Condition |
|---------|-----------|
| `URL_NOT_ALLOWED` | Domain not in allowlist |
| `METHOD_NOT_ALLOWED` | Method not GET or POST |
| `REDIRECT_DETECTED` | Redirects are forbidden |
| `PAYLOAD_TOO_LARGE` | Payload size exceeds limit |
| `MISSING_URL` | URL field missing |
| `UNSAFE_SCHEME` | Non-HTTPS scheme |

## Configuration

```python
from backend.core.capabilities.network_strict import NetworkConfig

config = NetworkConfig(
    allowed_domains={"api.openai.com", "api.anthropic.com"},
    allowed_methods={"GET", "POST"},
    max_payload_bytes=1024 * 1024,  # 1MB
    forbid_cookies=True,
    forbid_redirects=True,
    https_only=True,
)
```

## Example

```python
from backend.core.capabilities.network_strict import NetworkFetch

result = NetworkFetch.execute({
    "url": "https://api.openai.com/v1/models",
    "method": "GET",
    "timeout": 30,
}, config)
```

## Non-Goals
- No WebSocket support
- No cookie handling
- No automatic retries
- No redirect following
- No HTTP/2 support
- No file upload/download
