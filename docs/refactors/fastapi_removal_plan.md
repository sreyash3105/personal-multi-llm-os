# PR-STYLE REFACTOR PLAN

## Version
1.0
**Status:** APPROVED
**Date:** 2025-12-27

---

## EXECUTIVE SUMMARY

This plan describes the systematic removal of FastAPI HTTP layer and transition to local-first execution.

**Total Estimated Effort:**
- Analysis and Design: 12-16 hours
- Code Removal: 4-6 hours
- Local Runner Implementation: 32-40 hours
- Test Updates: 12-16 hours
- Verification and Validation: 8-12 hours
- **Total: 68-90 hours (1.7-2.2 weeks realistic)**

---

## PHASE 1: ANALYSIS AND DESIGN

### Objectives
- Map all HTTP entrypoints to core function calls
- Identify all dependencies on FastAPI/Pydantic
- Design local runner architecture
- Define context passing strategy
- Define state management without HTTP

### Deliverables
- Complete file removal list with LOC estimates
- Integration point inventory
- Local runner architecture specification
- Risk assessment for each removed component

---

## PHASE 2: CODE REMOVAL

### Files to Remove (~1,200 LOC total)

#### A. HTTP Server & Application Layer
1. **backend/code_server.py** (502 lines)
   - FastAPI app instance
   - All route definitions
   - All API models (Pydantic)
   - Escalation logic
   - **Estimate:** 0.5 hours

#### B. Router Layer (11 files, ~700 LOC total)
1. **backend/modules/router/api_router.py**
   - Intent router with HTTP endpoints
   - **Estimate:** 1 hour

2. **backend/modules/router/approval_router.py**
   - Approval decision endpoints
   - **Estimate:** 0.5 hours

3. **backend/modules/router/confirmation_router.py**
   - Confirmation flow endpoints
   - **Estimate:** 0.5 hours

4. **backend/modules/router/permission_router.py**
   - Permission management endpoints
   - **Estimate:** 0.5 hours

5. **backend/modules/router/stt_router.py**
   - STT router with HTTP endpoints
   - **Estimate:** 0.5 hours

6. **backend/modules/router/tts_router.py**
   - TTS router with HTTP endpoints
   - **Estimate:** 0.5 hours

#### C. Additional Router Components
7. **backend/modules/automation/router.py**
   - Automation decision endpoints
   - **Estimate:** 0.5 hours

8. **backend/modules/chat/chat_ui.py**
   - Chat UI serving via FastAPI
   - **Estimate:** 0.5 hours

#### D. Dashboard & Telemetry
9. **backend/modules/telemetry/dashboard.py**
   - Dashboard serving and computation
   - **Estimate:** 0.5 hours

**Total Router Layer Removal Estimate: 4 hours**

---

## PHASE 3: LOCAL RUNNER IMPLEMENTATION

### Architecture Overview

**OLD ARCHITECTURE:**
```
FastAPI App → Routers → Core Modules → Execution
     ↓              ↓
  HTTP Context  Pydantic Models
```

**NEW ARCHITECTURE:**
```
Local Runner → Direct Function Calls → Core Modules
     ↓              ↓
  Explicit Context  Objects  Direct Python Objects
```

### Design Principles
1. **Explicit Context Passing**
   - No implicit request/response objects
   - All context passed as explicit dictionaries
   - Context lifecycle is manual: create → pass → receive → destroy

2. **Function Call Semantics**
   - Direct Python function calls (not RPC)
   - Return values are Python objects (not deserialized from HTTP)
   - No async/sync translation layer

3. **State Management**
   - Sessions are Python dictionaries (not HTTP cookies)
   - Security contexts are explicit objects
   - No middleware-based state

4. **Error Handling**
   - Standard Python exceptions (not HTTPException)
   - No HTTP status codes for core errors
   - No request/response model validation errors

### Components to Create

#### A. Context Manager (backend/core/context_manager.py)
**Purpose:** Create and manage execution context objects

**Responsibilities:**
- Create context objects with unique IDs
- Track context lifecycle
- Provide thread-safe context access
- Ensure context cleanup

**Estimate:** 4-6 hours

#### B. Local Runner (backend/core/local_runner.py)
**Purpose:** Main entry point for AIOS execution

**Responsibilities:**
- Parse command-line arguments
- Create execution context
- Route to appropriate core module
- Handle errors gracefully
- Return results as plain text or JSON
- Telemetry logging integration

**Estimate:** 12-16 hours

#### C. CLI Entry Point (backend/cli/main.py)
**Purpose:** Command-line interface for AIOS

**Responsibilities:**
- Argument parsing (click or argparse)
- Command routing (code, study, automation, tools)
- Configuration loading
- Error handling
- Help text

**Estimate:** 8-12 hours

**Total Local Runner Estimate: 24-34 hours**

---

## PHASE 4: INTEGRATION PRESERVATION

### Integration Points Must Preserve

#### 1. Pattern Recording Integration (4 Critical Points)

**Point A: Refused Outcomes**
- Old: HTTP endpoint → pattern_aggregator.record_pattern()
- New: Local runner must call pattern_aggregator.record_pattern()
- Context Required: profile_id, session_id, triggering_action, pattern_details, related_failure_id

**Point B: Friction Confirmation**
- Old: HTTP endpoint timing measurement → detect_immediate_confirm_after_friction()
- New: Local runner must measure confirmation time and call detector
- Context Required: profile_id, session_id, friction_duration_seconds, confirmation_time_seconds, action_id

**Point C: Repeated Identical Requests**
- Old: HTTP endpoint request comparison → detect_identical_refusal_bypass()
- New: Local runner must track last request and call detector
- Context Required: profile_id, session_id, current_request, last_refusal_request, last_refusal_time

**Point D: Low-Confidence Attempts**
- Old: HTTP endpoint confidence tracking → detect_low_confidence_persistence()
- New: Local runner must track recent attempts and call detector
- Context Required: profile_id, session_id, current_confidence, confidence_threshold, recent_attempts

#### 2. Risk Assessment Integration

**Requirement:** preserve assess_risk() calls
- Context Required: mode, original_prompt, normalized_prompt, coder_output, reviewer_output, final_output
- Risk Model: {"risk_level": X, "tags": [...], "kind": "..."}

#### 3. Security Enforcement Integration

**Requirement:** preserve SecurityEngine.evaluate() calls
- Context Required: risk_score, operation_type, tool_name, context_tags

#### 4. Security Sessions Integration

**Requirement:** preserve create_security_session() calls
- Context Required: profile_id, scope, auth_level, ttl_seconds, max_uses, secret

#### 5. Escalation Logic Integration

**Requirement:** preserve should_escalate() and inject_escalation_comment()
- Context Required: judge_result (dict with scores), current code context

#### 6. History Logging Integration

**Requirement:** preserve history_logger.log() calls
- Context Required: kind, mode, original_prompt, normalized_prompt, coder_output, reviewer_output, final_output, escalated, escalation_reason, judge, models, risk

---

## PHASE 5: RISK MITIGATION STRATEGIES

### Risk 1: Breaking Risk Assessment
**Cause:** Direct function calls lose HTTP request context

**Mitigation:**
- Pass full context objects explicitly
- Maintain request metadata in context
- Reconstruct HTTP-like context where needed for compatibility

### Risk 2: Breaking Security Enforcement
**Cause:** Direct calls bypass SecurityEngine evaluation

**Mitigation:**
- Call SecurityEngine.evaluate() before every sensitive operation
- Pass SecurityDecision to execution functions
- Enforce SecurityDecision.auth_level manually

### Risk 3: Breaking Escalation Logic
**Cause:** Direct calls lose HTTP-based trigger context

**Mitigation:**
- Reconstruct escalation triggers manually
- Maintain escalation state in context
- Call should_escalate() with explicit context

### Risk 4: Breaking Pattern Recording
**Cause:** Direct calls lose HTTP request metadata

**Mitigation:**
- Preserve HTTP request metadata in context
- Extract trigger information explicitly
- Pass full metadata to pattern detectors

### Risk 5: Breaking History Logging
**Cause:** HTTP requests provide structured logging hooks

**Mitigation:**
- Call history_logger.log() with all same metadata
- Manually add HTTP-specific metadata (endpoint, method) where appropriate
- Maintain audit trail continuity

---

## PHASE 6: OBSERVABILITY PRESERVATION

### Signals Lost When HTTP Removed

1. **Request metadata** (endpoint, method, path, headers)
2. **Response metadata** (status_code, headers, timing)
3. **HTTP-specific errors** (4xx, 5xx, timeouts)
4. **Client identity** (IP, user-agent for audit)
5. **Session lifecycle** (creation, usage, expiration)

### Mitigation Strategies

#### Strategy A: Context Metadata Enrichment
- Add HTTP request/response fields to context objects
- Log HTTP-specific metadata to history_logger.log()
- Maintain audit trail compatibility

#### Strategy B: Structured Logging Wrapper
- Create logging wrapper that adds HTTP metadata
- Apply to all history_logger.log() calls
- Preserve observability patterns from HTTP layer

#### Strategy C: Explicit Event Sourcing
- Add explicit HTTP event types to history_logger
- Maintain separate HTTP observability log
- Dashboard can read both sources

---

## PHASE 7: TEST COVERAGE PLAN

### Critical Test Areas

#### A. Integration Point Tests (4 Critical)

**Test A1: Refused Outcomes Integration**
```python
def test_refused_outcome_records_pattern():
    context = {"profile_id": "test", "session_id": "test_session"}
    # Simulate refused outcome
    # Assert pattern_aggregator.record_pattern() was called with correct context
```

**Test A2: Friction Confirmation Integration**
```python
def test_friction_confirmation_records_pattern():
    context = {"profile_id": "test", "session_id": "test_session"}
    # Simulate immediate confirm (confirmation_time < 1 second)
    # Assert detect_immediate_confirm_after_friction() was called
```

**Test A3: Repeated Identical Requests Integration**
```python
def test_identical_request_records_pattern():
    context = {"profile_id": "test", "session_id": "test_session"}
    # Simulate identical request within time window
    # Assert detect_identical_refusal_bypass() was called
```

**Test A4: Low-Confidence Attempts Integration**
```python
def test_low_confidence_records_pattern():
    context = {"profile_id": "test", "session_id": "test_session"}
    # Simulate 3 attempts below threshold
    # Assert detect_low_confidence_persistence() was called
```

#### B. Core System Tests

**Test B1: Risk Assessment Preserved**
```python
def test_risk_assessment_direct_call():
    # Assert assess_risk() returns same result as HTTP version
    # Test with various modes and prompts
```

**Test B2: Security Enforcement Preserved**
```python
def test_security_enforcement_direct_call():
    # Assert SecurityEngine.evaluate() called before sensitive operations
    # Test SecurityDecision.auth_level enforced
```

**Test B3: Escalation Logic Preserved**
```python
def test_escalation_direct_call():
    # Assert should_escalate() returns same decision
    # Assert inject_escalation_comment() adds comment correctly
```

**Test B4: History Logging Preserved**
```python
def test_history_logging_direct_call():
    # Assert history_logger.log() called with all expected metadata
    # Test HTTP-specific metadata preservation
```

#### C. Local Runner Tests

**Test C1: Context Lifecycle**
```python
def test_context_creation_and_cleanup():
    # Assert context created with correct metadata
    # Assert context cleaned up after use
```

**Test C2: Direct Function Calls**
```python
def test_direct_module_invocation():
    # Assert core modules called directly
    # Assert no HTTP layer involved
```

**Test C3: Error Handling**
```python
def test_python_exception_handling():
    # Assert Python exceptions raised, not HTTPException
    # Assert standard error messages
```

### Test Update Estimates
- Integration Point Tests: 6-8 hours
- Core System Tests: 8-12 hours
- Local Runner Tests: 12-16 hours
- **Total Test Update Effort: 26-36 hours**

---

## PHASE 8: ROLLBACK STRATEGY

### Rollback Triggers
- Any test failure in preserved integration
- Any pattern recording failure
- Any risk assessment regression
- Any security enforcement bypass
- Any unexplained behavior change

### Rollback Procedure
1. **Immediate Rollback**
   - Restore FastAPI code from git
   - Ensure all integration points restored
   - Roll back to HTTP-based execution

2. **Root Cause Analysis**
   - Document why local runner failed
   - Update risk analysis
   - Review rollback triggers

3. **Alternative Path**
   - Consider parallel execution (HTTP + Local)
   - Consider adapter pattern instead of replacement
   - Incremental migration approach

### Rollback Time Estimate
- Code Restoration: 1-2 hours
- Testing: 2-4 hours
- Analysis: 2-4 hours
- **Total: 5-10 hours**

---

## EXECUTION ORDER

### Safe Removal Sequence (Parallel-Safe Where Possible)

1. **First:** Create local runner skeleton (no removal yet)
2. **Second:** Create context manager
3. **Third:** Create CLI entry point
4. **Fourth:** Update imports in local runner
5. **Fifth:** Update all tests to use local runner context
6. **Sixth:** Run all tests and verify passing
7. **Seventh:** Only then remove FastAPI files

### Critical Rule
**DO NOT REMOVE FASTAPI UNTIL LOCAL RUNNER TESTS PASS**

This prevents breaking the system during transition.

---

## ACCEPTANCE CONDITIONS

### Pre-Implementation Checklist

This plan must satisfy all conditions before implementation begins:

- [ ] All 6 required documentation files exist in /docs
- [ ] Integration point mapping documented
- [ ] Rollback strategy defined
- [ ] Risk mitigation strategies documented
- [ ] Test coverage plan complete
- [ ] File-by-file LOC estimates provided
- [ ] Dependencies to add identified
- [ ] Removal order specified (safe sequence)
- [ ] Critical rule documented (tests first, removal second)

### Post-Implementation Checklist

- [ ] All tests pass with local runner
- [ ] All 4 pattern recording points work
- [ ] Risk assessment preserves behavior
- [ ] Security enforcement preserved
- [ ] Escalation logic preserved
- [ ] History logging preserved with HTTP metadata
- [ ] Observability audit trail complete
- [ ] FastAPI successfully removed
- [ ] No core module required changes

---

## CHANGE CLASSIFICATION

**Type:** BEHAVIORAL_SHIFT (EXPECTED)

All changes are:
- Intentional
- Visible
- Documented
- Explainable
- Reversible

No silent changes.
No implicit changes.
No accidental drift.

---

## SIGN-OFF

**Plan Status:** APPROVED
**Total Estimated Effort:** 90-126 hours (including design, implementation, testing, verification)

**Ready for Documentation Phase:**
Create all 6 required markdown files under /docs directory before implementation.

**End of Plan**
