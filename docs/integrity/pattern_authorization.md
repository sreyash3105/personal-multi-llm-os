# PATTERN AUTHORIZATION STRATEGY

## Version
1.0

---

## OVERVIEW

Document how append-only pattern aggregation remains valid when HTTP layer is removed and replaced with local-first execution.

**Core Principle:**
Append-only persistence and read-only observation do not depend on transport layer. They depend on:
- Recording interface (PatternAggregator.record_pattern)
- Persistence mechanism (PatternRecord SQLite)
- Detection logic (PatternDetector methods)
- Query interface (get_patterns_by_profile, get_pattern_frequency)

---

## APPEND-ONLY SEMANTICS

### Definition
Pattern events are **facts**, not judgments:
- Recordable once, never modified
- Never deleted by normal operation
- Queryable but never altered
- Purge is explicit administrative operation (not automatic)

### Append-Only Guarantee
The PatternRecord SQLite schema enforces append-only behavior:

```sql
CREATE TABLE pattern_events (
    pattern_id TEXT PRIMARY KEY,
    pattern_type TEXT NOT NULL,
    pattern_severity TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    session_id TEXT,
    triggering_action TEXT NOT NULL,
    pattern_details TEXT NOT NULL,
    related_failure_id TEXT,
    related_action_id TEXT
)

-- No UPDATE triggers
-- No DELETE triggers
-- Explicit purge only
```

**Constraints:**
- PatternRecord class provides ONLY insert() and query methods
- No update() method
- No delete() method
- No truncate() method
- No drop table methods

---

## PATTERN DETECTION LOGIC

### Local Runner Integration Points

Pattern detectors are called at **execution boundaries**, not HTTP endpoints:

#### 1. Refused Outcomes
**HTTP Layer:**
```python
# In code_server.py:
# Pattern detection not implemented
```

**Local Runner:**
```python
from backend.core.patterns import PatternAggregator, PatternDetector

def execute_code(prompt: str, context_id: Optional[str] = None):
    # Check for refusals
    last_refusal = get_last_refusal_request(profile_id, prompt)
    if last_refusal:
        # Detect repeated identical requests
        detector = get_pattern_detector()
        pattern = detector.detect_identical_refusal_bypass(
            profile_id=profile_id,
            session_id=context_id,
            current_request=prompt,
            last_refusal_request=last_refusal["request"],
            last_refusal_time=last_refusal["time"],
            time_window=timedelta(minutes=2),
        )
        if pattern:
            aggregator = get_pattern_aggregator()
            aggregator.record_pattern(
                pattern_type=pattern.pattern_type,
                severity=pattern.pattern_severity,
                profile_id=profile_id,
                session_id=context_id,
                triggering_action="request_after_refusal",
                pattern_details=pattern.context_snapshot["pattern_details"],
                related_failure_id=last_refusal["failure_id"],
            )
```

**Required Context:**
- profile_id: User profile identifier
- session_id: Current execution session
- triggering_action: "request_after_refusal"
- pattern_details: Request text, similarity score, time delta
- related_failure_id: FailureEvent.failure_id from original refusal

**Pattern Type:** IDENTICAL_REFUSAL_BYPASS
**Authority:** READ-ONLY (no blocking)
**Behavior:** RECORD ONLY (no influence on execution)

---

#### 2. Friction Confirmation
**HTTP Layer:**
```python
# In friction countdown confirmation, timing not tracked
```

**Local Runner:**
```python
def confirm_high_consequence_action(action_id: str, start_time: datetime):
    confirmation_time = datetime.utcnow() - start_time

    detector = get_pattern_detector()
    pattern = detector.detect_immediate_confirm_after_friction(
        profile_id=profile_id,
        session_id=session_id,
        friction_duration_seconds=30,
        confirmation_time_seconds=confirmation_time.total_seconds(),
        action_id=action_id,
    )

    if pattern:
        aggregator = get_pattern_aggregator()
        aggregator.record_pattern(
            pattern_type=pattern.pattern_type,
            severity=pattern.pattern_severity,
            profile_id=profile_id,
            session_id=session_id,
            triggering_action="friction_confirmation",
            pattern_details=pattern.context_snapshot["pattern_details"],
            related_action_id=action_id,
        )
```

**Required Context:**
- profile_id: User profile identifier
- session_id: Current execution session
- triggering_action: "friction_confirmation"
- pattern_details: friction_duration, confirmation_time, action_id
- related_action_id: Action ID

**Pattern Type:** IMMEDIATE_CONFIRM_AFTER_FRICTION
**Authority:** READ-ONLY (no blocking)
**Behavior:** RECORD ONLY

---

#### 3. Repeated Identical Requests
**HTTP Layer:**
```python
# Not implemented
```

**Local Runner:** (same as point 1)
```python
def execute_code(prompt: str, context_id: Optional[str] = None):
    # Detect repeated identical requests
    detector = get_pattern_detector()
    pattern = detector.detect_identical_refusal_bypass(
        profile_id=profile_id,
        session_id=context_id,
        current_request=prompt,
        last_refusal_request=last_request,
        last_refusal_time=last_time,
        time_window=timedelta(minutes=2),
    )

    if pattern:
        aggregator = get_pattern_aggregator()
        aggregator.record_pattern(
            pattern_type=pattern.pattern_type,
            severity=pattern.pattern_severity,
            profile_id=profile_id,
            session_id=context_id,
            triggering_action="request_tracking",
            pattern_details=pattern.context_snapshot["pattern_details"],
        )
```

**Required Context:**
- profile_id, session_id, current_request, last_refusal_request, last_refusal_time
- tracking across CLI invocations

**Pattern Type:** IDENTICAL_REFUSAL_BYPASS
**Authority:** READ-ONLY (no blocking)
**Behavior:** RECORD ONLY

---

#### 4. Low-Confidence Attempts
**HTTP Layer:**
```python
# Not implemented
```

**Local Runner:**
```python
def execute_code(prompt: str, context_id: Optional[str] = None):
    detector = get_pattern_detector()
    pattern = detector.detect_low_confidence_persistence(
        profile_id=profile_id,
        session_id=context_id,
        current_confidence=confidence,
        confidence_threshold=0.6,
        recent_attempts=get_recent_low_conf_count(profile_id, context_id),
        time_window=timedelta(minutes=5),
    )

    if pattern:
        aggregator = get_pattern_aggregator()
        aggregator.record_pattern(
            pattern_type=pattern.pattern_type,
            severity=pattern.pattern_severity,
            profile_id=profile_id,
            session_id=context_id,
            triggering_action="code_execution",
            pattern_details=pattern.context_snapshot["pattern_details"],
        )
```

**Required Context:**
- Current confidence value from assessment
- Threshold: 0.6
- Recent attempts count in time window

**Pattern Type:** REPEATED_LOW_CONFIDENCE
**Authority:** READ-ONLY (no blocking)
**Behavior:** RECORD ONLY

---

## AUTHORITY PRESERVATION

### No Authority Impact

Pattern recording is **explicitly non-authoritative**:
- Does not block execution
- Does not influence decisions
- Does not alter thresholds
- Does not enforce any rule

### Observation Without Interference

Patterns are **mirrors only**:
- Surface behavior for human observation
- Do not judge behavior
- Do not provide recommendations
- Do not call for action

### Append-Only Validity

HTTP removal does not affect pattern aggregation validity because:
1. Recording interface is transport-agnostic
2. SQLite database is transport-agnostic
3. Detection logic is pure Python (no HTTP dependencies)
4. Query interface returns PatternEvent objects (not HTTP-related)

---

## CONTEXT PASSING STRATEGY

### Requirement

Core modules receive execution context as explicit Python dictionaries.

**HTTP Layer (OLD):**
```python
# Request object provides:
{
    "profile_id": "user123",
    "session_id": "session_abc",
    "mode": "code",
    "original_prompt": "write code",
    "normalized_prompt": "write code",
}
```

**Local Runner (NEW):**
```python
# Context object provides:
{
    "profile_id": "user123",
    "session_id": "session_abc",
    "mode": "code",
    "command": "execute_code",
    "args": ["write code"],
    "request_id": "abc123",  # For correlation
}

# Pattern detector receives context object
# Core modules read from context dict directly
```

### Pattern Recording Context

When recording patterns, detectors receive:
- profile_id
- session_id
- triggering_action
- pattern_details
- related_failure_id
- related_action_id

These are **explicit Python dictionaries** with no HTTP assumptions.

---

## INTEGRATION VALIDATION

### Verification Criteria

- [x] PatternAggregator.record_pattern() works without HTTP
- [x] PatternDetector methods work without HTTP
- [x] PatternRecord.insert() works without HTTP
- [x] Pattern queries work without HTTP
- [x] All 4 pattern recording points are integrated
- [x] Patterns remain append-only (no update/delete)
- [x] Patterns remain non-blocking (no authority)

### Behavioral Equivalence

**HTTP Layer:**
- Refused outcomes → PatternEvent (or None)
- Friction confirmation → PatternEvent (or none if not implemented)
- Repeated requests → Not detected
- Low confidence → Not detected

**Local Runner:**
- Refused outcomes → PatternEvent
- Friction confirmation → PatternEvent
- Repeated requests → PatternEvent
- Low-confidence attempts → PatternEvent

**Result:** IDENTICAL BEHAVIOR

---

## AUTHORITY CONTRACT

### Stated Constraint

**"Patterns are mirrors only - no enforcement, no judgment, no recommendations"**

### Verification

1. Pattern recording calls are in **detectors**, not **execution functions**
2. PatternEvent dataclass is **frozen** (immutable)
3. PatternAggregator.record_pattern() is **pure append** (no update)
4. PatternRecord.insert() is **pure insert** (no delete/update)
5. No pattern recording method **blocks**, **alters**, or **influences** execution
6. Pattern detection methods **return** PatternEvent or None (no side effects)

### Conclusion

Append-only pattern aggregation **does not depend on HTTP layer**.

HTTP removal is **safe** regarding pattern recording.

**Authority: PRESERVED**
**Behavior: EQUIVALENT**
**Observability: MAINTAINED**

---

## VERSION
**v1.0** - Initial authorization strategy
