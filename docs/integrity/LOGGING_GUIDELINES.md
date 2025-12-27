# Local AI OS - Logging Guidelines

## Overview
This document defines logging standards for the Local AI OS to ensure consistent, debuggable, and observable system behavior.

## Core Principles

### 1. Structured Logging
- Use structured logging with consistent field names
- Include contextual information in `extra` dict
- Use appropriate log levels for different scenarios

### 2. Request Correlation
- Every API request gets a unique `request_id`
- Long-running operations maintain request context
- Session context tracks user interactions

### 3. Component-Based Organization
- Loggers are organized by component hierarchy: `ai_os.{component}.{subcomponent}`
- Components: `api`, `models`, `queue`, `storage`, `security`

### 4. Performance Awareness
- Debug logs only in development
- Info level for normal operations
- Warning/Error for issues requiring attention
- Include timing information for operations >100ms

## Log Levels & Usage

### DEBUG
- Internal state changes
- Function entry/exit (in development)
- Detailed troubleshooting information
- Example: `"Model qwen2.5-coder loaded successfully"`

### INFO
- Normal operational events
- API request/response cycles
- Component lifecycle events
- Example: `"API POST /api/code completed in 2.34s"`

### WARNING
- Degraded functionality
- Retry scenarios
- Configuration issues
- Example: `"Feature pyautogui unavailable - using mock mode"`

### ERROR
- Component failures
- Data corruption
- Security violations
- Example: `"Database connection failed - switching to read-only mode"`

### CRITICAL
- System-wide failures
- Data loss scenarios
- Security breaches
- Example: `"All model endpoints unavailable - system shutdown"`

## Standard Log Formats

### API Requests
```
INFO ai_os.api.code abc12345 - API POST /api/code started (user: user123, prompt_length: 150)
INFO ai_os.api.code abc12345 - API POST /api/code completed in 2.34s (status: success)
```

### Model Operations
```
INFO ai_os.models.qwen2.5-coder abc12345 - Model inference started (input_tokens: 512, operation: code_generation)
INFO ai_os.models.qwen2.5-coder abc12345 - Model inference completed in 1.23s (output_tokens: 256)
```

### Queue Operations
```
INFO ai_os.queue.manager abc12345 - Queue job_enqueued (job_id: job_789, profile_id: prof_123, kind: code)
WARNING ai_os.queue.manager abc12345 - Queue job_failed (job_id: job_789, error: timeout)
```

### Security Events
```
WARNING ai_os.security.events abc12345 - Security path_traversal_attempted (user: user123, path: ../../../etc/passwd)
ERROR ai_os.security.events abc12345 - Security authentication_failed (user: unknown, reason: invalid_token)
```

### Performance Issues
```
WARNING ai_os.storage.history abc12345 - Slow operation detected (operation: db_write, duration: 0.156s, threshold: 0.1s)
```

## Implementation Examples

### Basic Component Logger
```python
from backend.core.observability import get_logger

logger = get_logger('api.code')

def generate_code(request):
    logger.info("Code generation started", extra={
        'user_id': request.user_id,
        'prompt_length': len(request.prompt)
    })
    # ... processing ...
    logger.info("Code generation completed", extra={
        'duration': processing_time,
        'output_length': len(result)
    })
```

### Performance Timing
```python
from backend.core.observability import get_logger, PerformanceTimer

logger = get_logger('models.llm')

def call_model(prompt):
    with PerformanceTimer(logger, "model_inference",
                         model_name="qwen2.5-coder",
                         input_tokens=len(prompt.split())) as timer:
        result = ollama_call(prompt)
        timer.context['output_tokens'] = len(result.split())
        return result
```

### Request Context
```python
from backend.core.observability import set_request_context, generate_request_id

@app.middleware("http")
async def add_request_context(request, call_next):
    request_id = generate_request_id()
    set_request_context(request_id, getattr(request.state, 'session_id', None))

    logger = get_logger('api.core')
    logger.info(f"Request started: {request.method} {request.url.path}")

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    logger.info(f"Request completed in {duration:.3f}s",
               extra={'status_code': response.status_code, 'duration': duration})

    return response
```

## Configuration

### Development
```python
from backend.core.observability import setup_logging
setup_logging(level="DEBUG", log_file=Path("logs/ai_os_debug.log"))
```

### Production
```python
setup_logging(level="INFO", log_file=Path("/var/log/ai_os/ai_os.log"))
```

## Monitoring Integration

### Health Checks
- Log parsing for error rates
- Performance metric extraction
- Component availability monitoring

### Alerts
- Error rate thresholds
- Performance degradation
- Security event patterns

### Dashboards
- Request throughput by endpoint
- Model inference latency percentiles
- Queue depth and processing rates
- Error rates by component

## Migration Path

### Phase 1: Infrastructure
- [x] Create observability module
- [x] Define logging schema
- [ ] Replace print() statements with proper logging
- [ ] Add request correlation to API endpoints

### Phase 2: Component Migration
- [ ] Update API endpoints with structured logging
- [ ] Add performance timing to model calls
- [ ] Enhance queue operation logging
- [ ] Add security event logging

### Phase 3: Monitoring
- [ ] Implement health check endpoints
- [ ] Add metrics collection
- [ ] Create alerting rules
- [ ] Build monitoring dashboards

## Best Practices

### 1. Context Over Verbosity
- Prefer structured fields over long messages
- Include IDs for correlation (request_id, job_id, user_id)
- Use consistent field names across components

### 2. Performance Consciousness
- Avoid expensive operations in logging code
- Use lazy evaluation for debug logs
- Batch similar log messages when possible

### 3. Security Awareness
- Never log sensitive data (passwords, tokens, PII)
- Use appropriate log levels for security events
- Consider log aggregation security

### 4. Operational Readiness
- Include actionable information in error logs
- Use consistent error categorization
- Support log-based debugging workflows

This logging system provides comprehensive observability while maintaining performance and security standards suitable for production deployment.