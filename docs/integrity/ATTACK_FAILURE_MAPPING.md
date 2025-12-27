# ATTACK TO FAILURE MAPPING TABLE

## AIOS Failure Articulation Layer - Artifact 4

This table maps all known adversarial attacks to specific failure types.

**Version**: 1.0
**Last Updated**: 2025-12-27

---

## SECTION 1: FOUNDATIONAL ATTACKS (CURRENT AIOS)

### Attack F1: Risk Score as Implicit Authority

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| F1 | SCALAR_COLLAPSE | HIGH | CONTINUE | REQUIRED | Risk scoring collapses multi-dimensional concerns (impact, authority, scope) into single scalar, hiding governance behind numeric threshold |
| F1 | HIDDEN_GOVERNANCE | HIGH | CONTINUE | REQUIRED | Boundary thresholds become de facto policy without explicit acknowledgment as governance |
| F1 | RISK_TUNING_SENSITIVITY | MEDIUM | CONTINUE | OPTIONAL | Small threshold changes produce large authority shifts, making governance fragile |

### Attack F2: TTL & Usage Limits Do Not Bound Cognitive Authority

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| F2 | ABOUNDED_EXECUTION | HIGH | CONTINUE | REQUIRED | TTL limits time, not scope; usage caps limit count, not impact |
| F2 | IMPACT_VS_COUNT_ERROR | HIGH | CONTINUE | REQUIRED | One high-impact action is equivalent to many low-impact ones, violating boundedness principle |
| F2 | AUTHORITY_LEAKAGE | MEDIUM | CONTINUE | OPTIONAL | Permissions may be used for broader scope than originally authorized |

### Attack F3: Session-Based Approval Temporal Drift

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| F3 | TEMPORAL_DRIFT | HIGH | HALT | REQUIRED | Approvals outlive mental context that produced them |
| F3 | TEMPORAL_MISALIGNMENT | HIGH | CONTINUE | REQUIRED | Concurrency causes approval/action misalignment |
| F3 | TEMPORAL_STALENESS | MEDIUM | CONTINUE | REQUIRED | Human intent decays faster than system permissions, causing stale authority |

### Attack F4: Fall-Through Behavior Masks Failure

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| F4 | INVISIBLE_FAILURE | HIGH | CONTINUE | REQUIRED | Failure is hidden as graceful handling, masking dysfunction |
| F4 | FALLTHROUGH_FAILURE | MEDIUM | CONTINUE | OPTIONAL | Ambiguous intent falls through without explicit acknowledgment |
| F4 | INTENT_AMBIGUITY | MEDIUM | CONTINUE | REQUIRED | System appears responsive while failing intent resolution |

### Attack F5: History Logs Create False Confidence

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| F5 | EPISTEMIC_OVERCONFIDENCE | HIGH | CONTINUE | REQUIRED | Humans infer completeness or causality from partial logs |
| F5 | FALSE_CAUSALITY | HIGH | CONTINUE | REQUIRED | Logs imply causal relationships that may not exist |
| F5 | NARRATIVE_FRAGILITY | MEDIUM | CONTINUE | OPTIONAL | Partial history feels complete, creating false confidence |

---

## SECTION 2: ROADMAP ATTACKS (FUTURE AIOS)

### Attack R1: Constitutional Layer Creates Meta-Authority

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| R1 | META_AUTHORITY | CRITICAL | HALT | REQUIRED | Meta-governance layer becomes de facto decision-maker, concentrating authority |
| R1 | AUTHORITY_CONCENTRATION | HIGH | CONTINUE | REQUIRED | Power moves upward rather than outward, violating distributed authority principle |

### Attack R2: Observability Creates Performance Pressure

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| R2 | COGNITIVE_FRAMING | HIGH | CONTINUE | REQUIRED | Engineers optimize for what is visible; invisible failures deprioritized |
| R2 | OBSERVABILITY_GAP | MEDIUM | CONTINUE | OPTIONAL | System drifts toward "good-looking" behavior; truth becomes presentation-aligned |
| R2 | GOVERNANCE_DRIFT | MEDIUM | CONTINUE | DEFERRED | Accumulated local optimizations create uncoordinated behavior changes |

### Attack R3: Cycle Formalization Hardens Wrong Abstractions

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| R3 | ABSTRACTION_WRONG | HIGH | CONTINUE | REQUIRED | Not all human intent is cyclical; forced terminal states oversimplify reality |
| R3 | REALITY_MISMATCH | HIGH | CONTINUE | REQUIRED | System optimizes for closure, not correctness |

### Attack R4: Event-Driven Truth is Fragmentary by Nature

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| R4 | FALSE_CAUSALITY | HIGH | CONTINUE | REQUIRED | Event ordering does not equal causality |
| R4 | NARRATIVE_FRAGILITY | HIGH | CONTINUE | REQUIRED | Missing events distort narratives; replay produces plausible but false histories |

### Attack R5: Governance Load Shifts Failure to Humans

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| R5 | HUMAN_BOTTLENECK | HIGH | CONTINUE | REQUIRED | Human-in-the-loop becomes limiting factor at scale |
| R5 | HUMAN_FATIGUE | MEDIUM | CONTINUE | REQUIRED | Approval fatigue increases, causing rubber-stamping |
| R5 | HUMAN_RUBBER_STAMP | MEDIUM | CONTINUE | REQUIRED | Precedent overrides scrutiny; safety decays without explicit rule violation |

### Attack R6: Safety Mechanisms Become Aversion Systems

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| R6 | OVER_SAFETY_AVERSION | HIGH | CONTINUE | REQUIRED | Excessive blocking trains users to work around system |
| R6 | FAIL_OPEN_PRESSURE | HIGH | HALT | REQUIRED | Uncertainty is common; shadow workflows emerge |
| R6 | BOUNDARY_VIOLATION | MEDIUM | CONTINUE | REQUIRED | Safety is bypassed, not broken; users create unauthorized workflows |

### Attack R7: Future You is the Most Likely Adversary

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| R7 | GOVERNANCE_DRIFT | HIGH | CONTINUE | REQUIRED | Temporary bypasses become permanent; exceptions accumulate |
| R7 | POLICY_CEREMONIALITY | CRITICAL | HALT | REQUIRED | Constitution becomes ceremonial; system drifts without explicit violation |
| R7 | COMPLEXITY_EXPLOSION | MEDIUM | CONTINUE | DEFERRED | Accumulated exceptions exceed human comprehension |

---

## SECTION 3: META ATTACK

### Attack M1: AIOS Assumes Rational Governance

| Attack ID | Failure Type | Severity | Execution Impact | Human Visibility | Justification |
|-----------|-------------|----------|------------------|-----------------|----------------|
| M1 | HUMAN_BOTTLENECK | HIGH | CONTINUE | REQUIRED | Humans are inconsistent, fatigable, and have limited attention span |
| M1 | HUMAN_FATIGUE | MEDIUM | CONTINUE | REQUIRED | Repeated approvals degrade scrutiny over time |
| M1 | SCALING_OVERFLOW | HIGH | CONTINUE | REQUIRED | System assumes ideal human behavior at scale; reality does not match |

---

## MAPPING SUMMARY STATISTICS

### By Failure Type Count

| Failure Type | Count | Affected Attacks |
|-------------|--------|------------------|
| TEMPORAL_DRIFT | 1 | F3 |
| TEMPORAL_MISALIGNMENT | 1 | F3 |
| TEMPORAL_STALENESS | 1 | F3 |
| SCALAR_COLLAPSE | 1 | F1 |
| HIDDEN_GOVERNANCE | 1 | F1 |
| RISK_TUNING_SENSITIVITY | 1 | F1 |
| ABOUNDED_EXECUTION | 1 | F2 |
| IMPACT_VS_COUNT_ERROR | 1 | F2 |
| AUTHORITY_LEAKAGE | 2 | F2, F1 |
| INVISIBLE_FAILURE | 1 | F4 |
| FALLTHROUGH_FAILURE | 1 | F4 |
| INTENT_AMBIGUITY | 1 | F4 |
| EPISTEMIC_OVERCONFIDENCE | 1 | F5 |
| FALSE_CAUSALITY | 2 | F5, R4 |
| NARRATIVE_FRAGILITY | 2 | F5, R4 |
| META_AUTHORITY | 1 | R1 |
| AUTHORITY_CONCENTRATION | 1 | R1 |
| COGNITIVE_FRAMING | 1 | R2 |
| OBSERVABILITY_GAP | 1 | R2 |
| GOVERNANCE_DRIFT | 2 | R2, R7 |
| ABSTRACTION_WRONG | 1 | R3 |
| REALITY_MISMATCH | 1 | R3 |
| HUMAN_BOTTLENECK | 2 | R5, M1 |
| HUMAN_FATIGUE | 2 | R5, M1 |
| HUMAN_RUBBER_STAMP | 1 | R5 |
| OVER_SAFETY_AVERSION | 1 | R6 |
| FAIL_OPEN_PRESSURE | 1 | R6 |
| BOUNDARY_VIOLATION | 1 | R6 |
| POLICY_CEREMONIALITY | 1 | R7 |
| COMPLEXITY_EXPLOSION | 1 | R7 |

### By Severity Count

| Severity | Count | Percentage |
|----------|--------|------------|
| CRITICAL | 2 | 10.5% |
| HIGH | 15 | 78.9% |
| MEDIUM | 13 | 68.4% |
| LOW | 0 | 0% |

*Note: Some attacks map to multiple failure types, so total exceeds 19 attacks.*

### By Execution Impact Count

| Execution Impact | Count | Percentage |
|-----------------|--------|------------|
| HALT | 4 | 21.1% |
| CONTINUE | 15 | 78.9% |
| GRACEFUL_DEGRADE | 0 | 0% |

### By Human Visibility Count

| Human Visibility | Count | Percentage |
|-----------------|--------|------------|
| REQUIRED | 17 | 89.5% |
| OPTIONAL | 2 | 10.5% |
| DEFERRED | 1 | 5.3% |
| NONE | 0 | 0% |

*Note: Some failures map to multiple visibility requirements across different attacks.*

---

## IMPLEMENTATION NOTES

### Priority for Implementation

**Immediate Priority (CRITICAL/HIGH + HALT):**
1. R1 - META_AUTHORITY (if building constitutional layer)
2. R6 - FAIL_OPEN_PRESSURE
3. R7 - POLICY_CEREMONIALITY
4. F3 - TEMPORAL_DRIFT (HALT variant)

**High Priority (HIGH + CONTINUE):**
1. F1 - SCALAR_COLLAPSE, HIDDEN_GOVERNANCE
2. F2 - ABOUNDED_EXECUTION, IMPACT_VS_COUNT_ERROR
3. F3 - TEMPORAL_MISALIGNMENT
4. F4 - INVISIBLE_FAILURE
5. F5 - EPISTEMIC_OVERCONFIDENCE, FALSE_CAUSALITY
6. All R-series HIGH failures

**Medium Priority (MEDIUM + CONTINUE):**
1. Remaining MEDIUM severity failures

### Detection Strategy

For each failure type, detection should:

1. **Explicit Check**: Add if-statement or assertion
2. **Context Capture**: Include relevant state in context_snapshot
3. **Failure Creation**: Instantiate FailureEvent with correct parameters
4. **Surfacing**: Follow Failure Surfacing Contract rules

**Example Detection Pattern:**

```python
# Detecting F3: TEMPORAL_DRIFT
def check_temporal_drift(session_grant_time: datetime, now: datetime) -> Optional[FailureEvent]:
    drift_threshold_minutes = 5  # Configurable

    if (now - session_grant_time).total_seconds() > drift_threshold_minutes * 60:
        return FailureEvent(
            failure_type=FailureType.TEMPORAL_DRIFT,
            severity=Severity.HIGH,
            execution_impact=ExecutionImpact.HALT,
            human_visibility=HumanVisibility.REQUIRED,
            origin_component=OriginComponent.SECURITY_SESSIONS,
            related_attack="F3",
            description=(
                f"Session approval granted {(now - session_grant_time).total_seconds() / 60:.1f} "
                f"minutes ago exceeds drift threshold of {drift_threshold_minutes} minutes. "
                f"User's mental context has likely decayed. "
                f"Fresh authorization required."
            ),
            context_snapshot={
                "session_grant_time": session_grant_time.isoformat(),
                "current_time": now.isoformat(),
                "drift_minutes": (now - session_grant_time).total_seconds() / 60,
                "threshold_minutes": drift_threshold_minutes,
            }
        )
    return None
```

### No Auto-Recovery

This mapping does NOT authorize:
- Automatic session refresh on temporal drift
- Automatic fallback to different authorization
- Automatic retry on failure
- Automatic threshold adjustment

All mapped failures must:
- Be surfaced to human
- Be logged to audit trail
- Stop execution if HALT
- Continue only if explicitly CONTINUE

---

## VERSION CONTROL

- **v1.0** (2025-12-27): Initial mapping of all F1-F5, R1-R7, M1 attacks

Changes to this table require:
1. Approval from AIOS governance body
2. Version increment
3. Update to all dependent systems
4. Re-run of failure detection tests

**End of Mapping Table**
