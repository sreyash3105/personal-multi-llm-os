# LOCAL RUNNER ARCHITECTURE

## Version
1.0

---

## OVERVIEW

Local runner provides direct, in-process execution of AIOS core functionality without HTTP/API layer.

**Architecture:**
```
Local Runner
    ↓
Context Manager (Stateful)
    ↓
Direct Function Calls
    ↓
Core Modules (Stateless)
```

---

## DESIGN PRINCIPLES

### 1. Explicit Context Passing
- No implicit request/response objects
- All context passed as explicit dictionaries
- Context lifecycle is manual (create → use → destroy)

### 2. Function-Call Semantics
- Direct Python function calls (not RPC)
- Return values are Python objects (not deserialized)
- No async/sync translation layer

### 3. State Management
- Sessions are Python dictionaries (not HTTP cookies)
- Security contexts are explicit objects
- No middleware-based state

### 4. Error Handling
- Standard Python exceptions (not HTTPException)
- No HTTP status codes for core errors
- Plain error messages

---

## COMPONENTS

### A. Context Manager (backend/core/context_manager.py)

**Purpose:** Create and manage execution context objects

**Responsibilities:**
- Create unique context ID
- Track context metadata (profile_id, session_id, mode)
- Provide thread-safe context storage
- Ensure context cleanup after execution

**Public API:**
```python
def create_context(profile_id: Optional[str], session_id: Optional[str], mode: str) -> Context
def get_current_context() -> Context
def destroy_context(context_id: str) -> None
def set_context_metadata(key: str, value: Any) -> None
```

**Estimate:** 4-6 hours

---

### B. Local Runner (backend/core/local_runner.py)

**Purpose:** Main entry point for AIOS execution

**Responsibilities:**
- Parse command-line arguments
- Create execution context
- Route commands to appropriate core modules
- Handle errors gracefully
- Return results as plain text or JSON
- Telemetry logging integration

**Public API (CLI):**
```python
def execute_code(prompt: str, context_id: Optional[str] = None) -> str
def execute_study(prompt: str, context_id: Optional[str] = None) -> str
def execute_automation(prompt: str, context_id: Optional[str] = None) -> str
def execute_tools(tool_name: str, args: Dict, context_id: Optional[str] = None) -> str
```

**Estimate:** 12-16 hours

---

### C. CLI Entry (backend/cli/main.py)

**Purpose:** Command-line interface for local runner

**Responsibilities:**
- Argument parsing (click or argparse)
- Command routing (code, study, automation, tools)
- Configuration loading
- Help text

**Commands:**
```bash
aios code "generate function that sorts a list"
aios study "explain this concept"
aios automation "click button on screen"
aios tools "delete file.txt"
```

**Estimate:** 8-12 hours

---

## CONTEXT LIFECYCLE

```
1. Local Runner creates context
   ↓
2. Context passed to core module (as explicit dict)
   ↓
3. Core module reads from context
   ↓
4. Core module returns result (as Python object)
   ↓
5. Local Runner receives result
   ↓
6. Local Runner destroys context
```

---

## ERROR HANDLING STRATEGY

### HTTP Layer (Removed)
- HTTPException → HTTP status code
- Request validation → 4xx
- Server errors → 5xx
- Timeout → request timeout

### Local Runner (New)
- Core module exceptions → Python exception
- Context missing → ValueError
- Tool not found → KeyError
- Validation error → custom exception

---

## TELEMETRY INTEGRATION

### HTTP Layer
- history_logger.log() called with HTTP-specific metadata
- Request/response timing
- Endpoint accessed
- Client identity (IP, user-agent)

### Local Runner (New)
- history_logger.log() called with execution metadata
- Context ID (for correlation)
- Command type
- Execution time
- Success/failure

---

## STATE MANAGEMENT

### HTTP Layer (Removed)
- HTTP sessions (cookies)
- Request/response objects
- Middleware state
- Background tasks

### Local Runner (New)
- Context dictionaries (in-memory)
- Explicit lifecycle (create → use → destroy)
- Thread-local storage for concurrent contexts

---

## ARCHITECTURE DIAGRAM

```
┌─────────────────┐
│   Local Runner │
└───────┬────────┘
        │
        ↓
    ┌─────────────────┐
    │  Context Manager │
    └───────┬────────┘
            │
            ↓
        │
    ┌─────────────────┐
    │  Core Modules   │
    │  - Code Pipeline │
    │  - Study Module   │
    │  - Tools Runtime │
    │  - Automation     │
    │  - Pattern Agg.   │
    └───────┬────────┘
            │
            ↓
    ┌─────────────────┐
    │  History Logger  │
    │  & Telemetry     │
    └─────────────────┘
```

---

## INTEGRATION POINTS

### From HTTP to Local Runner

1. **Risk Assessment**
   - HTTP: assess_risk(mode, prompt, original_prompt, coder_output, reviewer_output, final_output)
   - Local: Pass risk_context dict, extract fields
   - Module Modification: backend/modules/code/pipeline.py to accept risk_context parameter

2. **Security Enforcement**
   - HTTP: SecurityEngine.evaluate(risk_score, operation_type, tool_name, context_tags)
   - Local: Pass risk_context dict, extract fields
   - Module Modification: backend/modules/code/pipeline.py to call SecurityEngine.evaluate() with explicit context

3. **Pattern Recording - Refused Outcomes**
   - HTTP: Non-Action Report emitted, system continues
   - Local: Call pattern_aggregator.record_pattern() with context
   - Module Modification: backend/modules/code/pipeline.py to call pattern_aggregator after refusal

4. **Pattern Recording - Friction Confirmation**
   - HTTP: Not implemented
   - Local: Call pattern_detector.detect_immediate_confirm_after_friction()
   - Module Modification: backend/modules/code/pipeline.py to add friction timing tracking

5. **Pattern Recording - Repeated Requests**
   - HTTP: Not implemented
   - Local: Call pattern_detector.detect_identical_refusal_bypass()
   - Module Modification: backend/modules/code/pipeline.py to track last request

6. **Pattern Recording - Low Confidence**
   - HTTP: Not implemented
   - Local: Call pattern_detector.detect_low_confidence_persistence()
   - Module Modification: backend/modules/code/pipeline.py to track confidence attempts

7. **Security Sessions**
   - HTTP: create_security_session(profile_id, scope, auth_level, ...)
   - Local: Call create_security_session() with context
   - Module Modification: backend/modules/code/pipeline.py to store session_id in context

8. **Escalation**
   - HTTP: should_escalate(judge_result), inject_escalation_comment(code, reason)
   - Local: Call should_escalate() with context
   - Module Modification: backend/modules/code/pipeline.py to call escalation with context

9. **History Logging**
   - HTTP: history_logger.log({...}) with HTTP metadata
   - Local: Call history_logger.log() with execution metadata
   - Module Modification: backend/core/config.py or backend/modules/telemetry/history.py to enrich logger

---

## ESTIMATION SUMMARY

### Components to Create
- Context Manager: 4-6 hours
- Local Runner: 12-16 hours
- CLI Entry: 8-12 hours

### Modules to Modify
- Code Pipeline: 8-12 hours (risk, pattern, session, escalation integration)
- Study Module: 4-6 hours (pattern integration)
- Tools Runtime: 2-4 hours (pattern integration)
- Automation: 2-4 hours (pattern integration)
- Security Engine: 2-4 hours (context parameter support)

### Total Estimated Effort
- Core Components: 32-58 hours
- Tests: 12-16 hours
- **Total: 44-74 hours (1.9-2.8 weeks)**

---

## DEPENDENCIES

### No New Dependencies Required
- Uses existing backend.core modules
- Uses existing backend.modules.core modules
- Uses existing backend.core.patterns module
- Uses standard library (no pip installs needed)

---

## COMPLETION CRITERIA

Local runner is complete when:

- [ ] Context Manager created
- [ ] Local Runner created
- [ ] CLI Entry created
- [ ] All integration points mapped
- [ ] All core modules modified
- [ ] Tests created/updated
- [ ] HTTP layer removed (optional, after tests pass)

---

## VERSION
**v1.0** - Initial architecture document
