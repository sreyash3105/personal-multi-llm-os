# TEST COVERAGE PLAN

## Version
1.0

---

## OVERVIEW

Complete test coverage plan for FastAPI removal and local-first execution transition.

**Purpose:**
Ensure all 4 critical pattern recording points are tested with local runner context
Verify core behavior pre/post refactor is equivalent
Prove pattern aggregation remains append-only and non-blocking

---

## CRITICAL TEST AREAS

### Area 1: Pattern Recording at Refused Outcomes

#### Test 1.1: Refused Outcome Records Pattern
**HTTP Layer (OLD):**
- File: backend/code_server.py
- Behavior: Non-Action Report emitted, system continues

**Local Runner (NEW):**
- File: backend/core/local_runner.py
- Behavior: Same Non-Action Report emitted, system continues

**Test Case:**
```python
def test_refused_outcome_records_pattern():
    """
    Verify that refused outcomes trigger pattern recording.
    """
    from backend.core.patterns import PatternType, PatternAggregator
    from backend.core.pattern_record import PatternRecord

    aggregator = PatternAggregator()
    profile_id = "test_user"
    session_id = "test_session"

    # Simulate refused outcome
    failure_event = {
        "failure_id": "failure_123",
        "failure_type": "IDENTICAL_REFUSAL_BYPASS",
        "pattern_severity": "MEDIUM",
        "timestamp": datetime.utcnow().isoformat(),
        "context_snapshot": {
            "profile_id": profile_id,
            "session_id": session_id,
            "triggering_action": "refusal",
            "pattern_details": {
                "user_request": "delete file",
                "refusal_reason": "Unsafe operation",
            }
        },
    }

    # Simulate PatternEvent from history_logger.log()
    # Local runner calls pattern_aggregator.record_pattern()
    expected_context = {
        "profile_id": profile_id,
        "session_id": session_id,
        "triggering_action": "refusal",
        "pattern_details": failure_event["context_snapshot"]["pattern_details"],
        "related_failure_id": failure_event["failure_id"],
    }

    # Execute
    pattern = aggregator.record_pattern(
        pattern_type=PatternType.IDENTICAL_REFUSAL_BYPASS,
        pattern_severity="MEDIUM",
        profile_id=profile_id,
        session_id=session_id,
        triggering_action="refusal",
        pattern_details=expected_context["pattern_details"],
        related_failure_id=failure_event["failure_id"],
        related_action_id=None,
    )

    # Verify
    assert pattern is not None
    assert pattern.pattern_id == "IDENTICAL_REFUSAL_BYPASS"
    assert pattern.pattern_severity == "MEDIUM"
    assert pattern.context_snapshot["profile_id"] == profile_id

    # Verify record exists in database
    patterns = PatternRecord.query_by_profile(profile_id=profile_id, limit=10)
    assert len(patterns) == 1
    assert patterns[0]["pattern_type"] == "IDENTICAL_REFUSAL_BYPASS"
```

**Estimate:** 6-8 hours

---

#### Test 1.2: Friction Confirmation Records Pattern
**HTTP Layer (OLD):**
- File: backend/code_server.py
- Integration: friction countdown with confirmation button
- Current Behavior: No pattern recording

**Local Runner (NEW):**
- File: backend/core/local_runner.py
- Integration: friction countdown, user confirms
- Expected Behavior: Pattern detector measures time, calls record_pattern()

**Test Case:**
```python
def test_friction_confirmation_records_pattern():
    """
    Verify that immediate confirmation after friction triggers pattern recording.
    """
    from backend.core.patterns import PatternType, PatternAggregator
    from backend.core.pattern_record import PatternRecord

    detector = PatternDetector()
    aggregator = PatternAggregator()
    profile_id = "test_user"
    session_id = "test_session"
    action_id = "action_123"

    # Simulate 30-second friction countdown, user confirms in 0.5 seconds
    start_time = datetime.utcnow()
    confirm_time = start_time + timedelta(seconds=0.5)
    friction_duration = 30

    # Expected: IMMEDIATE_CONFIRM_AFTER_FRICTION pattern recorded
    detector = get_pattern_detector()
    pattern = detector.detect_immediate_confirm_after_friction(
        profile_id=profile_id,
        session_id=session_id,
        friction_duration_seconds=friction_duration,
        confirmation_time_seconds=0.5,
        action_id=action_id,
    )

    assert pattern is not None
    assert pattern.pattern_type == PatternType.IMMEDIATE_CONFIRM_AFTER_FRICTION

    # Verify record
    patterns = PatternRecord.query_by_profile(profile_id=profile_id, limit=10)
    assert len(patterns) == 1
    assert patterns[0]["pattern_type"] == "IMMEDIATE_CONFIRM_AFTER_FRICTION"
```

**Estimate:** 6-8 hours

---

#### Test 1.3: Repeated Identical Requests Records Pattern
**HTTP Layer (OLD):**
- File: backend/code_server.py
- Integration: None (not implemented)

**Local Runner (NEW):**
- File: backend/core/local_runner.py
- Integration: CLI command executes repeatedly
- Expected Behavior: Pattern detector tracks last request, detects repetition

**Test Case:**
```python
def test_repeated_identical_requests_records_pattern():
    """
    Verify that repeated identical requests trigger pattern recording.
    """
    from backend.core.patterns import PatternType, PatternAggregator
    from backend.core.pattern_record import PatternRecord

    detector = PatternDetector()
    aggregator = PatternAggregator()
    profile_id = "test_user"
    session_id = "test_session"

    # Simulate first request
    first_request = "delete file.txt"
    first_time = datetime.utcnow() - timedelta(minutes=5)

    # Store as "last" (via context)
    # detector.detect_identical_refusal_bypass() will compare to this

    # Simulate second identical request within 2-minute window
    second_time = datetime.utcnow()
    pattern = detector.detect_identical_refusal_bypass(
        profile_id=profile_id,
        session_id=session_id,
        current_request=first_request,
        last_refusal_request=first_request,
        last_refusal_time=first_time,
        time_window=timedelta(minutes=2),
    )

    # Verify
    assert pattern is not None
    assert pattern.pattern_type == PatternType.IDENTICAL_REFUSAL_BYPASS

    # Verify record exists
    patterns = PatternRecord.query_by_profile(profile_id=profile_id, limit=10)
    assert len(patterns) == 1
```

**Estimate:** 6-8 hours

---

#### Test 1.4: Low-Confidence Attempts Records Pattern
**HTTP Layer (OLD):**
- File: backend/code_server.py
- Integration: None (not implemented)

**Local Runner (NEW):**
- File: backend/core/local_runner.py
- Integration: Code pipeline, study, automation with risk assessment
- Expected Behavior: Pattern detector tracks recent low-confidence attempts

**Test Case:**
```python
def test_low_confidence_attempts_records_pattern():
    """
    Verify that repeated low-confidence attempts trigger pattern recording.
    """
    from backend.core.patterns import PatternType, PatternAggregator
    from backend.core.pattern_record import PatternRecord

    detector = PatternDetector()
    aggregator = PatternAggregator()
    profile_id = "test_user"
    session_id = "test_session"

    # Simulate 3 attempts with confidence 0.5 (below 0.6 threshold)
    # Store attempt history in context
    attempts = []
    for i in range(3):
        attempts.append({
            "confidence": 0.5,
            "timestamp": datetime.utcnow().isoformat(),
        })
        detector = get_pattern_detector()
        pattern = detector.detect_low_confidence_persistence(
            profile_id=profile_id,
            session_id=session_id,
            current_confidence=0.5,
            confidence_threshold=0.6,
            recent_attempts=len(attempts),
            time_window=timedelta(minutes=5),
        )

    # 4th attempt at 0.7 (still below threshold, but 4th in window)
    attempts.append({
        "confidence": 0.7,
        "timestamp": datetime.utcnow().isoformat(),
    })
    detector = get_pattern_detector()
    pattern = detector.detect_low_confidence_persistence(
        profile_id=profile_id,
        session_id=session_id,
        current_confidence=0.7,
        confidence_threshold=0.6,
        recent_attempts=len(attempts),
        time_window=timedelta(minutes=5),
    )

    assert pattern is not None
    assert pattern.pattern_type == PatternType.REPEATED_LOW_CONFIDENCE
    assert pattern.pattern_severity in ["LOW", "MEDIUM", "HIGH"]
    assert len(pattern.context_snapshot["attempts"]) == 4
```

**Estimate:** 8-10 hours

---

### Area 2: Core System Integrations

#### Test 2.1: Risk Assessment Preserved
**HTTP Layer (OLD):**
- File: backend/code_server.py, backend/modules/code/pipeline.py
- Integration: assess_risk(mode, prompt, coder_output, reviewer_output, final_output)
- Current Behavior: Risk object returned with level, tags, kind

**Local Runner (NEW):**
- File: backend/core/local_runner.py
- Integration: Direct function call to assess_risk(risk_context)
- Expected Behavior: Same risk object returned

**Test Case:**
```python
def test_risk_assessment_direct_call():
    """
    Verify that direct function calls to assess_risk work correctly.
    """
    from backend.modules.code.pipeline import assess_risk
    from backend.core.context_manager import create_context

    profile_id = "test_user"
    session_id = "test_session"
    context = create_context(profile_id, session_id)

    risk_context = {
        "mode": "code",
        "original_prompt": "write function x()",
        "normalized_prompt": "write function x()",
        "coder_output": "def x(): return 'output'",
        "reviewer_output": "",
        "final_output": "def x(): return 'output'",
    }

    risk_result = assess_risk(risk_context)

    # Verify structure
    assert "risk_level" in risk_result
    assert "tags" in risk_result
    assert "kind" in risk_result

    # Compare with HTTP layer behavior
    # Result should be structurally identical
    assert isinstance(risk_result, dict)
    assert len(risk_result) == 3  # risk_level, tags, kind
```

**Estimate:** 6-8 hours

---

#### Test 2.2: Security Enforcement Preserved
**HTTP Layer (OLD):**
- File: backend/code_server.py, backend/modules/security/security_engine.py
- Integration: SecurityEngine.evaluate(risk_score, operation_type, ...) called before execution

**Local Runner (NEW):**
- File: backend/core/local_runner.py
- Integration: Direct function call to SecurityEngine.evaluate()

**Test Case:**
```python
def test_security_enforcement_direct_call():
    """
    Verify that SecurityEngine.evaluate() is called before execution.
    """
    from backend.modules.security.security_engine import SecurityEngine

    profile_id = "test_user"
    session_id = "test_session"

    # Local runner creates context
    context = create_context(profile_id, session_id)

    # Simulate operation that requires security check
    risk_context = {
        "mode": "automation",
        "original_prompt": "delete file.txt",
        "normalized_prompt": "delete file.txt",
        "coder_output": "",
        "reviewer_output": "",
        "final_output": "",
    }

    # Should call SecurityEngine.evaluate()
    # Verify call is made

    # This test would mock the core modules to verify call
    # In practice, we'd verify by inspecting local_runner.py code
```

**Estimate:** 4-6 hours

---

#### Test 2.3: Security Sessions Preserved
**HTTP Layer (OLD):**
- File: backend/code_server.py, backend/modules/code/pipeline.py, backend/modules/security/security_sessions.py
- Integration: create_security_session(profile_id, scope, ...) called

**Local Runner (NEW):**
- File: backend/core/local_runner.py
- Integration: Direct function call to create_security_session()

**Test Case:**
```python
def test_security_sessions_preserved():
    """
    Verify that security sessions are created and tracked.
    """
    from backend.modules.security.security_sessions import create_security_session
    from backend.core.context_manager import create_context

    profile_id = "test_user"
    session_id = "test_session"

    context = create_context(profile_id, session_id)

    # Create session
    session = create_security_session(
        profile_id=profile_id,
        scope="file.delete",
        auth_level=3,
        ttl_seconds=300,
    )

    # Verify
    assert session is not None
    assert "session_id" in session

    # In practice, local runner stores session_id in context
    # for use in pattern recording
```

**Estimate:** 6-8 hours

---

#### Test 2.4: Escalation Logic Preserved
**HTTP Layer (OLD):**
- File: backend/code_server.py
- Integration: should_escalate(judge_result), inject_escalation_comment()
- Current Behavior: Escalation comment added to reviewer_output

**Local Runner (NEW):**
- File: backend/core/local_runner.py
- Integration: Direct function calls, escalation comment injection

**Test Case:**
```python
def test_escalation_logic_preserved():
    """
    Verify that escalation logic works without HTTP.
    """
    from backend.modules.code.pipeline import run_reviewer

    profile_id = "test_user"
    session_id = "test_session"

    # Local runner creates context
    context = create_context(profile_id, session_id)

    # Simulate high-risk judge result
    judge_result = {
        "confidence_score": 0.2,
        "conflict_score": 0.9,
        "judgement_summary": "High conflict, low confidence",
    }

    # Should trigger escalation
    escalation_decision, escalation_reason = should_escalate(judge_result)

    assert escalation_decision == True
    assert "auto-escalated to heavy review" in escalation_reason

    # Simulate reviewer output
    reviewer_output = "# Escalated due to:\n" + escalation_reason

    # Verify local runner can inject comment
    # (This would test local_runner.py modification)
```

**Estimate:** 6-8 hours

---

### Area 3: History Logging Preserved

#### Test 3.1: HTTP Request/Response Logging
**HTTP Layer (OLD):**
- File: backend/code_server.py, all router modules
- Integration: history_logger.log(kind, mode, prompt, coder_output, etc.)
- Current Behavior: Automatic logging with HTTP context

**Local Runner (NEW):**
- File: backend/core/local_runner.py
- Integration: Direct function call to history_logger.log()
- Expected Behavior: Same logging with added execution metadata

**Test Case:**
```python
def test_history_logging_preserved():
    """
    Verify that HTTP request/response logging is preserved.
    """
    from backend.modules.telemetry.history import history_logger

    profile_id = "test_user"
    session_id = "test_session"

    # Local runner creates context
    context = create_context(profile_id, session_id)

    # Simulate code execution (simple case)
    log_entry = {
        "kind": "code",
        "mode": "code",
        "original_prompt": "write hello",
        "normalized_prompt": "write hello",
        "coder_output": "print('hello')",
        "reviewer_output": "",
        "final_output": "print('hello')",
        "execution_time_ms": 150,
    }

    # Call history_logger.log()
    history_logger.log(log_entry)

    # Verify no exception raised
    # (Success is silent)
```

**Estimate:** 4-6 hours

---

#### Test 3.2: Error Handling Preservation
**HTTP Layer (OLD):**
- File: backend/code_server.py, all modules
- Integration: HTTPException raised, HTTP status codes returned

**Local Runner (NEW):**
- File: backend/core/local_runner.py
- Integration: Standard Python exceptions raised, error messages returned

**Test Case:**
```python
def test_error_handling_preserved():
    """
    Verify that error handling works without HTTP layer.
    """
    from backend.modules.code.pipeline import run_coder

    profile_id = "test_user"
    session_id = "test_session"

    context = create_context(profile_id, session_id)

    # Simulate error
    # (This would mock code module to raise exception)

    # Local runner catches exception
    try:
        result = run_coder("raise error", context=context)
    except Exception as e:
        # Should propagate
        assert str(e) == "raise error"
        raise

    # In practice, local_runner.py would:
    # 1. Catch exception
    # 2. Log error
    # 3. Return error message
    # 4. ContextManager.destroy_context() to cleanup
```

**Estimate:** 6-8 hours

---

### Area 4: Local Runner Core Tests

#### Test 4.1: Context Lifecycle
**Test Case:**
```python
def test_context_lifecycle():
    """
    Verify context creation, usage, and destruction work correctly.
    """
    from backend.core.context_manager import (
        create_context,
        get_current_context,
        destroy_context,
    )

    profile_id = "test_user"
    session_id = "test_session"

    # Create context
    ctx = create_context(profile_id, session_id)
    assert ctx is not None

    # Verify context is current
    current = get_current_context()
    assert current is not None
    assert current.session_id == session_id

    # Destroy context
    destroy_context(session_id)
    # Should not raise
```

**Estimate:** 4-6 hours

---

#### Test 4.2: Direct Function Calls
**Test Case:**
```python
def test_direct_function_calls():
    """
    Verify that core modules can be called directly.
    """
    from backend.modules.code.pipeline import run_coder
    from backend.modules.study import run_study
    from backend.modules.automation.executor import plan_and_execute

    profile_id = "test_user"
    session_id = "test_session"

    context = create_context(profile_id, session_id)

    # Try code
    result = run_coder("write hello", context=context)
    assert result == "hello" or result == "Error: ..."

    # Try study
    result = run_study("explain concept", context=context)
    assert result.startswith("Concept:")

    # Try automation
    result = plan_and_execute("click button", context=context, execute=False)
    assert isinstance(result, dict) or "plan" in result
```

**Estimate:** 6-8 hours

---

#### Test 4.3: Pattern Aggregator Integration
**Test Case:**
```python
def test_pattern_aggregator_integration():
    """
    Verify pattern aggregator works with local runner.
    """
    from backend.core.patterns import PatternAggregator
    from backend.core.pattern_record import PatternRecord

    profile_id = "test_user"
    session_id = "test_session"

    # Get aggregator
    aggregator = PatternAggregator()

    # Record pattern
    pattern = aggregator.record_pattern(
        pattern_type=PatternType.IDENTICAL_REFUSAL_BYPASS,
        pattern_severity="MEDIUM",
        profile_id=profile_id,
        session_id=session_id,
        triggering_action="test_action",
        pattern_details={"test": "data"},
    )

    assert pattern is not None

    # Verify record exists
    patterns = PatternRecord.query_by_profile(profile_id=profile_id, limit=10)
    assert len(patterns) == 1
```

**Estimate:** 4-6 hours

---

## PRE-IMPLEMENTATION CHECKLIST

Before writing tests:

- [ ] Pattern detectors are callable from local_runner.py
- [ ] ContextManager is callable from local_runner.py
- [ ] PatternAggregator is callable from local_runner.py
- [ ] PatternRecord is callable from local_runner.py
- [ ] All imports resolve correctly
- [ ] No HTTP layer dependencies remain

## IMPLEMENTATION ORDER

1. Create backend/core/context_manager.py
2. Create backend/core/local_runner.py
3. Create backend/cli/main.py
4. Update all core modules to accept context parameters
5. Update all 4 integration points in core modules
6. Create test/test_local_runner_integration.py
7. Create test/test_pattern_local_runner.py
8. Run all tests and verify passing
9. Update existing tests that call HTTP endpoints
10. Remove FastAPI files once tests pass

## EFFORT ESTIMATE

- Tests: 40-48 hours (all 4 critical areas + core)
- Implementation: 44-74 hours (context manager, local runner, module updates, CLI)
- Verification: 8-12 hours
- **Total: 93-134 hours (1.3-2.6.5.2 weeks realistic)**

---

## COMPLETION CRITERIA

Test coverage is complete when:

- [ ] All 4 pattern recording points have tests
- [ ] All core system integrations have tests
- [ ] History logging preservation verified
- [ ] Context lifecycle tested
- [ ] Direct function calls verified
- [ ] All tests pass consistently
- [ ] No behavioral regression detected

---

## VERSION
**v1.0** - Initial test coverage plan
