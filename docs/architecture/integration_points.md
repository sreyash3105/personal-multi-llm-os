# INTEGRATION POINTS MAPPING

## Version
1.0

---

## OVERVIEW

This document maps all integration points that previously relied on FastAPI HTTP layer to direct function calls.

**Purpose:**
- Provide complete inventory of points requiring local runner integration
- Support risk analysis for preserved behaviors
- Guide implementation of local runner

---

## INTEGRATION POINTS

### Category: Pattern Recording (4 Critical Points)

#### Point 1: Refused Outcomes
**HTTP Layer:**
- File: backend/code_server.py
- Endpoint: /api/code
- Current Behavior: FailureEvent emitted, system continues

**Local Runner Integration:**
- Context Manager: Create execution context object with profile_id, session_id
- Behavior: After non-action report, call pattern_aggregator.record_pattern()
- Detection: No detection needed (refusal is explicit)
- Pattern Type: IDENTICAL_REFUSAL_BYPASS
- Required Context: profile_id, session_id, triggering_action, pattern_details, related_failure_id

**Risk:** LOW (straightforward mapping)

**Implementation Priority:** 1

---

#### Point 2: Friction Confirmation
**HTTP Layer:**
- File: backend/code_server.py
- Integration: friction countdown with confirmation button
- Current Behavior: No pattern recording implemented

**Local Runner Integration:**
- Context Manager: Create execution context with profile_id, session_id, action_id
- Behavior: Measure confirmation time (end_timestamp - start_timestamp)
- Detection: Call detect_immediate_confirm_after_friction()
- Pattern Type: IMMEDIATE_CONFIRM_AFTER_FRICTION
- Required Context: profile_id, session_id, friction_duration_seconds, confirmation_time_seconds, action_id
- Additional: Store start_timestamp in context for timing

**Risk:** MEDIUM (requires timing state management)

**Implementation Priority:** 2

---

#### Point 3: Repeated Identical Requests
**HTTP Layer:**
- File: backend/code_server.py
- Endpoint: /api/code
- Current Behavior: No request tracking or comparison

**Local Runner Integration:**
- Context Manager: Track last_request in context
- Behavior: Store normalized current request in context
- Detection: On each request, compare with last_request using sequence matching
- Pattern Type: IDENTICAL_REFUSAL_BYPASS
- Required Context: profile_id, session_id, current_request, last_refusal_request, last_refusal_time, time_window
- Detection Call: detect_identical_refusal_bypass()
- Additional: time_window configurable (default: 2 minutes)

**Risk:** MEDIUM (requires stateful context management)

**Implementation Priority:** 2

---

#### Point 4: Low-Confidence Attempts
**HTTP Layer:**
- File: backend/code_server.py
- Endpoint: /api/code
- Current Behavior: No confidence tracking

**Local Runner Integration:**
- Context Manager: Track recent low-confidence attempts in context
- Behavior: Increment counter on each attempt below threshold
- Detection: Call detect_low_confidence_persistence() when threshold reached
- Pattern Type: REPEATED_LOW_CONFIDENCE
- Required Context: profile_id, session_id, current_confidence, confidence_threshold, recent_attempts, time_window
- Additional: Threshold configurable (default: 0.6), window configurable (default: 5 minutes)

**Risk:** MEDIUM (requires stateful counter in context)

**Implementation Priority:** 3

---

### Category: Core System Integrations (Critical)

#### Point 5: Risk Assessment
**HTTP Layer:**
- Files: backend/code_server.py, backend/modules/code/pipeline.py
- Endpoint: /api/code
- Current Behavior: assess_risk() called with HTTP context

**Local Runner Integration:**
- Context Manager: Create risk_context dictionary
- Behavior: Pass explicit risk_context object to core modules
- Integration: Modify core modules to accept risk_context parameter
- Pattern Recording: No pattern detection needed here
- Required Context: mode, original_prompt, normalized_prompt, coder_output, reviewer_output, final_output
- Risk Model: No change, still uses assess_risk()
- Additional: Ensure all risk calls propagate context through call chain

**Risk:** LOW (interface change, no logic alteration)

**Implementation Priority:** 1

---

#### Point 6: Security Enforcement
**HTTP Layer:**
- Files: backend/code_server.py, backend/modules/code/pipeline.py
- Integration: SecurityEngine.evaluate() called before actions

**Local Runner Integration:**
- Context Manager: Call SecurityEngine.evaluate() explicitly
- Behavior: Pass SecurityDecision to execution functions
- Pattern Recording: No pattern detection needed here
- Required Context: risk_score, operation_type, tool_name, context_tags
- Additional: Ensure SecurityEngine singleton is initialized in local runner

**Risk:** LOW (direct call pattern)

**Implementation Priority:** 1

---

#### Point 7: Security Sessions
**HTTP Layer:**
- Files: backend/code_server.py, backend/modules/code/pipeline.py
- Integration: create_security_session() called

**Local Runner Integration:**
- Context Manager: Track session_id in execution context
- Behavior: Call create_security_session() and store session_id in context
- Pattern Recording: No pattern detection needed here
- Required Context: profile_id, scope, auth_level, ttl_seconds, max_uses, secret
- Additional: Ensure security sessions SQLite database accessible from local runner

**Risk:** LOW (database path compatibility)

**Implementation Priority:** 2

---

#### Point 8: Escalation Logic
**HTTP Layer:**
- Files: backend/code_server.py, backend/modules/code/pipeline.py
- Integration: should_escalate(), inject_escalation_comment() called

**Local Runner Integration:**
- Context Manager: Call should_escalate() and get escalation reason
- Behavior: Store escalation decision in context
- Pattern Recording: No pattern detection needed here
- Required Context: judge_result (dict with scores)
- Pattern Type: N/A (not a misuse pattern, but behavior to preserve)
- Additional: If escalated, call reviewer_output generation

**Risk:** MEDIUM (escalation logic complexity)

**Implementation Priority:** 2

---

#### Point 9: History Logging
**HTTP Layer:**
- Files: backend/code_server.py, backend/modules/code/pipeline.py, backend/modules/automation/router.py, etc.
- Integration: history_logger.log() called with HTTP context

**Local Runner Integration:**
- Context Manager: Add HTTP metadata to history calls
- Behavior: Wrap history_logger.log() to enrich with HTTP context
- Pattern Recording: No pattern detection needed here
- Required Context: All existing parameters + http_metadata (endpoint, method, path)
- Additional: Ensure HTTP-specific metadata is only added when HTTP layer was involved
- Detection: Check if context contains "http_endpoint" flag
- Integration: Modify backend.core.config to export HTTP-aware logger

**Risk:** HIGH (observability preservation critical)

**Implementation Priority:** 2

---

### Category: Pattern Detection Integrations (Preserved Behaviors)

#### Point 10: Warning Dismissal Detection
**HTTP Layer:**
- File: None (not implemented in current code)

**Status:** NOT APPLICABLE

**Risk:** N/A

---

#### Point 11: Simplified Request Detection
**HTTP Layer:**
- File: None (not implemented in current code)

**Status:** NOT APPLICABLE

**Risk:** N/A

---

#### Point 12: Repeated Friction Cancel Detection
**HTTP Layer:**
- File: None (not implemented in current code)

**Status:** NOT APPLICABLE

**Risk:** N/A

---

## SUMMARY

### Critical Points: 9
### Total Points: 12
### Priority 1 Points: 5
### Priority 2 Points: 4
### Priority 3 Points: 1

### High Risk Points: 1 (History Logging)
### Medium Risk Points: 5

### Not Applicable Points: 3

---

## IMPLEMENTATION GUIDELINES

### General Rules
1. All pattern recording calls must use pattern_aggregator.record_pattern()
2. All context objects must be created via ContextManager
3. Context must be explicitly passed through call chains
4. No state persistence between requests (local runner = fresh start)
5. All errors must be handled explicitly and logged

### Risk Mitigation
1. Implement ContextManager first (Priority 1)
2. Add pattern recording to high-risk integration points first
3. Preserve all existing behavior (no optimization, no smoothing)
4. Maintain observability via enriched history logging

---

## COMPLETION CRITERIA

This mapping is complete when:

- [ ] All 12 integration points are documented
- [ ] Local runner integration strategy defined for each point
- [ ] Risk assessment provided for each integration
- [ ] Implementation priority assigned
- [ ] Data requirements (context) specified

**Status:** IN PROGRESS
