# FAILURE SURFACING CONTRACT

## AIOS Failure Articulation Layer - Artifact 3

This contract defines WHEN and HOW failures are raised in AIOS.

### Contract Version
**Version**: 1.0
**Effective**: Immediate
**Binding**: All AIOS components

---

## 1. FAILURE RAISING RULES

### 1.1 WHEN to Raise Failure

A component MUST raise a FailureEvent when ANY of the following conditions occur:

#### Authority Violations
- Permission granted at wrong scope is being used
- Approval session is stale (excessive temporal drift)
- Multiple components claim authority for same decision
- Hidden governance is detected in enforcement path
- Risk score is being used to make decisions without explicit acknowledgment

#### Temporal Misalignment
- Approval timestamp differs from execution timestamp beyond threshold
- Context snapshot at grant time does not match execution context
- Session TTL has expired but session is still valid in database
- Approval exists for action that no longer matches user intent

#### Ambiguity and Intent Failure
- Intent classification confidence below threshold
- Router falls through to default pipeline without acknowledgment
- User input contains multiple conflicting intents that cannot be resolved
- System cannot map user request to known operations

#### Boundary Violation
- Component accesses database or state it should not
- Module directly calls another module's internal functions
- Tool execution bypasses security checks
- Configuration is modified at runtime without explicit lifecycle

#### Observability Gaps
- Critical decision is made without logging
- Event sequence implies causality without explicit causation marker
- Failure is masked as "graceful handling"
- Partial data is presented as complete

#### Human Factor Failure (Detection Only)
- Component detects pattern of repeated fast approvals (potential rubber-stamping)
- User repeatedly rejects or bypasses similar requests
- Approval latency exceeds expected human response time
- User requests exceed cognitive capacity (excessive notifications)

### 1.2 WHEN NOT to Raise Failure

A component MUST NOT raise a FailureEvent for:

- Expected operational conditions (e.g., no data available)
- User cancellation or explicit refusal
- Known safe fallbacks that are documented
- Non-impacting performance degradation (e.g., 5ms latency increase)
- Logging and telemetry operations themselves

---

## 2. EXECUTION IMPACT RULES

### 2.1 HALT Execution

Execution MUST halt immediately when FailureEvent has:

- **Severity**: CRITICAL
- **Execution Impact**: HALT

When HALT occurs:

1. Component MUST:
   - Log the FailureEvent to persistent storage
   - Stop all further processing of current request
   - Return error response with failure_id
   - Trigger UI notification if visibility is REQUIRED

2. Component MUST NOT:
   - Attempt retry
   - Fallback to alternative path
   - Continue processing other parts of request
   - Suppress the failure

3. System Behavior:
   - Current operation is cancelled
   - No state changes occur
   - User is presented with failure description
   - System waits for human intervention

### 2.2 CONTINUE Execution

Execution MAY continue when FailureEvent has:

- **Execution Impact**: CONTINUE or GRACEFUL_DEGRADE

When CONTINUE occurs:

1. Component MUST:
   - Log the FailureEvent to persistent storage
   - Continue processing with awareness of failure
   - Include failure_id in downstream context
   - Document limitation in output

2. Component MAY:
   - Continue with reduced functionality (GRACEFUL_DEGRADE)
   - Add warning indicators to response
   - Collect additional telemetry

3. Component MUST NOT:
   - Attempt to repair or auto-recover
   - Ignore the failure (must be logged)
   - Pretend failure did not occur

### 2.3 GRACEFUL_DEGRADE Execution

When execution impact is GRACEFUL_DEGRADE:

1. Component MUST:
   - Explicitly document what capability is degraded
   - Inform user of limitation
   - Log both failure and degradation state
   - Continue with degraded functionality only

2. System MUST NOT:
   - Upgrade back to full capability without new authorization
   - Hide the fact that degradation occurred

---

## 3. HUMAN NOTIFICATION RULES

### 3.1 REQUIRED Visibility

When HumanVisibility = REQUIRED:

1. Component MUST:
   - Surface failure to UI immediately
   - Block dismiss until human acknowledgment
   - Display failure description and failure_id
   - Provide option to view full context_snapshot

2. UI Requirements:
   - Failure must appear in prominent notification area
   - Cannot be dismissed without explicit acknowledgment
   - Must link to failure documentation or explanation
   - Must indicate related_attack if present

3. Timing:
   - Notification within 100ms of failure detection
   - No batching with other notifications
   - No deferral allowed

### 3.2 OPTIONAL Visibility

When HumanVisibility = OPTIONAL:

1. Component MAY:
   - Display failure in non-intrusive manner
   - Log to system logs
   - Include in audit trail

2. Component MUST NOT:
   - Block execution for notification display
   - Require user acknowledgment
   - Disrupt user workflow

### 3.3 DEFERRED Visibility

When HumanVisibility = DEFERRED:

1. Component MUST:
   - Log to persistent storage
   - Include in audit reports
   - Make available in failure dashboard

2. Component MUST NOT:
   - Display immediately
   - Trigger real-time notification

### 3.4 NONE Visibility

When HumanVisibility = NONE:

1. Component MUST:
   - Log to internal debugging logs only
   - Keep failure traceable but hidden from users

2. Permitted Use Cases ONLY:
   - Internal system health checks
   - Non-impacting performance metrics
   - Development/testing diagnostics

---

## 4. LOGGING AND AUDIT RULES

### 4.1 Mandatory Logging

ALL FailureEvents MUST be logged with:

1. Failure Event Schema
   - All required fields from failure_schema.py
   - Complete context_snapshot
   - Full description (no truncation)

2. Storage Requirements
   - Persistent storage (SQLite or equivalent)
   - No log rotation that deletes recent failures
   - Immutable once written (no updates or deletes)

3. Indexing Requirements
   - Searchable by failure_type
   - Searchable by timestamp
   - Searchable by origin_component
   - Searchable by related_attack

### 4.2 Audit Trail

For failures with severity >= MEDIUM:

1. Capture:
   - Request ID causing failure
   - Profile ID if applicable
   - Session ID if applicable
   - Input that triggered failure (sanitized)
   - Component stack trace

2. Audit Report:
   - Daily failure summary
   - Critical failure immediate alert
   - Failure trend analysis (count only, no inference)

### 4.3 Observability Integration

1. Structured Logging Format:
   ```json
   {
     "event_type": "FAILURE_EVENT",
     "failure_id": "...",
     "failure_type": "...",
     "severity": "...",
     "timestamp": "...",
     "origin_component": "...",
     "execution_impact": "...",
     "context_snapshot": {...}
   }
   ```

2. NO auto-aggregation of failures
3. NO statistical inference on failure patterns
4. NO ML-based failure prediction

---

## 5. FORBIDDEN ACTIONS

The following actions are STRICTLY FORBIDDEN during failure handling:

### 5.1 Auto-Recovery
- MUST NOT automatically retry after failure
- MUST NOT fallback to alternative implementation
- MUST NOT attempt to repair corrupted state
- MUST NOT suppress and continue without logging

### 5.2 Learning and Adaptation
- MUST NOT learn from failure patterns
- MUST NOT adjust thresholds based on failure frequency
- MUST NOT auto-tune parameters after failures
- MUST NOT retrain or update models on failures

### 5.3 Inference and Generalization
- MUST NOT infer user intent from failures
- MUST NOT generalize from specific failure cases
- MUST NOT assume patterns from limited data
- MUST NOT create new failure types at runtime

### 5.4 Suppression
- MUST NOT hide failures from audit trail
- MUST NOT aggregate failures to hide frequency
- MUST NOT delay logging of critical failures
- MUST NOT modify failure descriptions after creation

---

## 6. FAILURE CHAINS

### 6.1 Related Failures

When one failure causes another:

1. Parent failure MUST:
   - Set related_failure_ids to include child failure
   - Complete its own lifecycle before child processes

2. Child failure MUST:
   - Include parent failure_id in related_failure_ids
   - Not attempt to correct parent failure

### 6.2 Failure Propagation

When failure propagates across components:

1. Each component MUST:
   - Log its own FailureEvent
   - Propagate original failure_id in context
   - Not mutate original failure

2. Component MUST NOT:
   - Replace failure with new one
   - Suppress original failure details
   - Create new failure type mid-flight

---

## 7. COMPLIANCE REQUIREMENTS

### 7.1 Component Implementation

Every AIOS component MUST:

1. Import failure_schema.FailureEvent
2. Implement failure detection logic
3. Create FailureEvent on violation
4. Respect execution_impact (HALT vs CONTINUE)
5. Follow human_visibility rules
6. Log all failures to persistent storage

### 7.2 Validation

Before deployment, component MUST:

1. Demonstrate failure detection for all relevant failure types
2. Show HALT behavior for CRITICAL failures
3. Show CONTINUE behavior for MEDIUM/HIGH failures
4. Verify human notification for REQUIRED visibility
5. Confirm all failures are logged

### 7.3 Testing Requirements

Tests MUST include:

1. Failure scenario coverage
2. HALT execution verification
3. Notification trigger verification
4. Logging verification
5. NO auto-recovery verification

---

## 8. CONTRACT VIOLATION

Any component that violates this contract is itself in violation of:

- AIOS Sanctioned Failure Contract
- AIOS Fail-Closed Security Principle
- AIOS Observability Requirements

Contract violations MUST be reported as:

```python
FailureEvent(
    failure_type=FailureType.BOUNDARY_VIOLATION,
    severity=Severity.CRITICAL,
    execution_impact=ExecutionImpact.HALT,
    human_visibility=HumanVisibility.REQUIRED,
    origin_component=OriginComponent.<VIOLATING_COMPONENT>,
    description="Component violated Failure Surfacing Contract: [details]"
)
```

---

## 9. EXPLICIT NON-ACTION STATEMENT

This contract does NOT authorize:

- Auto-recovery mechanisms
- Failure pattern learning
- Adaptive threshold tuning
- Retry logic
- Suppression of failures
- Aggregation of failures
- Inference from failures
- Any action other than SURFACING, LOGGING, and HALTING

**If an action is not listed as permitted in this contract, it is forbidden.**

---

## 10. SIGN-OFF

This Failure Surfacing Contract is binding immediately upon:

1. Integration into AIOS core
2. Component implementation
3. Testing verification
4. Deployment to production

No phase-in period is permitted.
No exceptions are permitted.
No grandfathering of existing violations is permitted.

**End of Contract**
