# OBSERVABILITY PRESERVATION ANALYSIS

## Version
1.0

---

## OVERVIEW

Analysis of observability signals that will be lost when FastAPI HTTP layer is removed and replaced with local-first execution.

**Purpose:**
- Identify all HTTP-specific observability mechanisms
- Determine which signals must be preserved in local runner
- Propose mitigation strategies

---

## OBSERVABILITY SIGNALS IN FASTAPI LAYER

### 1. Request Metadata

#### 1.1 HTTP Request Object
**Location:** FastAPI's `Request` object

**Captured Information:**
- HTTP method (GET, POST, etc.)
- URL path
- Headers (cookies, user-agent, content-type)
- Query parameters
- Client IP address
- Request timestamp

**Loss:** HTTP request object no longer available

**Impact:** CRITICAL on audit trail reconstruction

#### 1.2 Response Metadata

**Location:** FastAPI response headers

**Captured Information:**
- HTTP status code (200, 404, 500, etc.)
- Content-Type header
- Content-Length header
- Server timing headers (if configured)
- Response timestamp

**Loss:** Response metadata no longer available

**Impact:** HIGH on failure diagnostics

---

### 2. Session Management

#### 2.1 HTTP Session Storage

**Location:** Middleware, session backends

**Captured Information:**
- Session ID
- Creation timestamp
- Last access timestamp
- Session data stored by session ID
- Session expiration time

**Loss:** Automatic session lifecycle management

**Impact:** CRITICAL on security audit

#### 2.2 State Management via Middleware

**Location:** middleware stack

**Captured Information:**
- Request state across middleware chain
- Context injection points
- State mutation tracking

**Loss:** Middleware-based state management

**Impact:** HIGH on behavior analysis

---

### 3. Structured Logging

#### 3.1 HTTP Request/Response Logging

**Location:** All endpoints

**Captured Information:**
- HTTP method and URL for every request
- Request headers (except sensitive)
- Request body (sanitized)
- Response status code
- Response headers (except sensitive)
- Processing time

**Loss:** Automatic HTTP request/response logging

**Impact:** MEDIUM on execution reconstruction

#### 3.2 Error Logging

**Location:** Global exception handlers, endpoint handlers

**Captured Information:**
- HTTPException status codes (4xx, 5xx)
- Stack traces for uncaught exceptions
- Exception type
- Error context

**Loss:** Automatic HTTP exception categorization

**Impact:** MEDIUM on failure diagnosis

#### 3.3 Timing Metrics

**Location:** Performance monitoring, middleware

**Captured Information:**
- Request start timestamp
- Request end timestamp
- Processing duration
- Endpoint-specific timings

**Loss:** Automatic request lifecycle timing

**Impact:** LOW on performance analysis

---

### 4. Client Identification

#### 4.1 IP Address Logging

**Location:** Middleware, request logging

**Captured Information:**
- Client IP address
- Proxy headers
- User-Agent string

**Loss:** Automatic client IP capture

**Impact:** CRITICAL on security audit

#### 4.2 Session Correlation

**Location:** All endpoints

**Captured Information:**
- Session ID from request
- Session ID in response (cookies, headers)
- Request-response correlation

**Loss:** Automatic session binding

**Impact:** MEDIUM on behavior reconstruction

---

### 5. Endpoint Metadata

#### 5.1 API Version

**Location:** FastAPI versioning, route tags

**Captured Information:**
- API version number
- Route tags for deprecation
- Documentation links

**Loss:** Built-in API versioning

**Impact:** LOW on change tracking

#### 5.2 Route Definition

**Location:** Route decorators, FastAPI router

**Captured Information:**
- Route path
- HTTP methods
- Route tags
- Middleware chain

**Loss:** Route metadata

**Impact:** LOW on endpoint mapping

---

## MITIGATION STRATEGIES

### Strategy 1: Request Context Objects

**Implementation:**
```python
# Context Manager creates explicit request context dictionary
class RequestContext:
    def __init__(self, command: str, args: List[str]):
        self.command = command
        self.args = args
        self.timestamp = datetime.utcnow().isoformat()
        self.request_id = str(uuid4())
        self.metadata = {}  # For custom fields

# CLI commands create RequestContext objects
# Local runner passes RequestContext to core modules
```

**Preserves:**
- Request ID (correlation)
- Command and arguments
- Timestamp
- Custom metadata

**Lost:** HTTP method, URL, headers, client IP

**Impact:** LOW
**Acceptable:** Core modules only need request content, not HTTP metadata

---

### Strategy 2: Response Metadata Logging

**Implementation:**
```python
# Local runner logs response metadata explicitly
class ResponseLogger:
    def log_response(self, result: Any, metadata: Dict):
        log_entry = {
            "request_id": self.context.request_id,
            "success": bool(result),
            "output_type": type(result).__name__,
            "timestamp": datetime.utcnow().isoformat(),
            "response_metadata": metadata,
        }
        history_logger.log(log_entry)
```

**Preserves:**
- Response success/failure
- Output type
- Custom response metadata

**Lost:** HTTP status codes, headers, timing

**Impact:** LOW
**Acceptable:** Core modules return values; local runner adds metadata

---

### Strategy 3: Session Management

**Implementation:**
```python
# Session Manager creates and tracks Python dicts
class SessionManager:
    def create_session(self, profile_id: str) -> str:
        session_id = str(uuid4())
        self.sessions[session_id] = {
            "profile_id": profile_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat(),
        }
        return session_id

    def update_session(self, session_id: str, metadata: Dict):
        if session_id in self.sessions:
            self.sessions[session_id].update(metadata)
            self.sessions[session_id]["last_accessed"] = datetime.utcnow().isoformat()
```

**Preserves:**
- Session lifecycle
- Session data
- Profile association

**Lost:** Automatic expiration, middleware state

**Impact:** LOW
**Acceptable:** Core modules use session IDs directly

---

### Strategy 4: Timing and Performance

**Implementation:**
```python
# Local runner tracks timing explicitly
class PerformanceTracker:
    def __init__(self):
        self.metrics = {}

    def track_operation(self, operation: str, duration_ms: float):
        timestamp = datetime.utcnow().isoformat()
        self.metrics[timestamp] = {
            "operation": operation,
            "duration_ms": duration_ms,
        }
```

**Preserves:**
- Operation timing
- Performance metrics

**Lost:** Automatic HTTP-level timing

**Impact:** LOW
**Acceptable:** Core modules can self-timing

---

### Strategy 5: Error Logging

**Implementation:**
```python
# Local runner logs exceptions explicitly
class ErrorLogger:
    def log_error(self, error: Exception, context: Dict):
        error_entry = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
            "request_id": self.context.request_id if hasattr(self, 'context') else None,
        }
        # Log to history_logger
        history_logger.log({"kind": "error", **error_entry})
```

**Preserves:**
- Exception type and message
- Error context
- Correlation with request

**Lost:** HTTPException, status codes, stack traces

**Impact:** MEDIUM
**Acceptable:** Core modules raise exceptions; local runner adds HTTP metadata

---

## CRITICAL SIGNALS NOT PRESERVED

1. **HTTP Request Object** (CRITICAL impact)
2. **HTTP Response Status Codes** (HIGH impact)
3. **Client IP Address** (CRITICAL impact)
4. **Automatic Session Management** (MEDIUM impact)
5. **Automatic Request/Response Logging** (MEDIUM impact)

## ACCEPTABLE LOSSES

1. **HTTP Method, URL, Headers** (LOW impact - core doesn't need them)
2. **HTTP Status Codes, Headers, Timing** (LOW impact - core returns values)
3. **Automatic Middleware State** (LOW impact - not needed)
4. **Automatic Session Expiration** (LOW impact - local runner manages)
5. **Route Metadata** (LOW impact - not needed)

## CONCLUSION

FastAPI removal will lose CRITICAL (3), HIGH (1), MEDIUM (3), LOW (3) observability signals.

However, core modules do not depend on these signals for correct behavior.

Local runner will implement explicit context objects, session management, and logging to preserve essential observability.

---

## VERSION
**v1.0** - Initial analysis and mitigation strategies
