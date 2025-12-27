# MEK-5: Failure as First-Class Output

**Failure is composable, explicit, and truthful. Failure is data, not UX.**

## Overview

MEK-5 makes failure composable, explicit, and truthful without:
- Summarization
- Softening
- Inference
- Guidance
- Recovery
- Mitigation

Failure becomes **data**, not UX.

## Philosophy

**Failure is data, not UX.**

Failure IS:
- Composable (ordered list of events)
- Explicit (structured fields only)
- Truthful (no interpretation)
- Terminal (no recovery)

Failure is NOT:
- Summarized or deduplicated
- Softened or mitigated
- Interpreted semantically
- Explained with "why"
- Provided with guidance
- Recovered or retried

## Files

```
mek5/
├── __init__.py                 # Package exports
├── failure_primitives.py        # Failure primitives
├── failure_guard.py             # Guard extensions
├── tests.py                    # Adversarial tests (20 tests)
├── requirements.txt             # Dependencies
├── BUILD_SUMMARY.md            # Implementation summary
└── example.py                  # Usage examples
```

## Usage

### Create a Failure Event

```python
from failure_primitives import create_failure_event, Phase, FailureType

failure = create_failure_event(
    failure_id="fail123",
    phase=Phase.MEK_3,
    failure_type=FailureType.MISSING_CONFIDENCE,
    triggering_condition="Confidence not provided",
    principal_id="user123",
)
```

### Create a Failure Composition

```python
from failure_primitives import create_failure_composition

composition = create_failure_composition(
    composition_id="comp_failures",
    failures=[failure1, failure2, failure3],
)
```

### Execute with Failure Tracking

```python
from failure_guard import get_failure_guard

# Get failure guard with MEK Guard
guard = get_mek_guard()  # From MEK-3
fail_guard = get_failure_guard(guard)

# Execute with failure tracking
result = fail_guard.execute_with_failure_tracking(
    capability_name="file_read",
    context={
        "principal_id": "user123",
        "confidence": 0.9,
    },
)

if result.get("is_success", False):
    print(f"Success: {result.get('data')}")
else:
    failure = result.get("failure")
    print(f"Failed: {failure.failure_type}")
    print(f"Condition: {failure.triggering_condition}")
```

### Get Failure Composition

```python
if fail_guard.has_failures():
    composition = fail_guard.get_failure_composition()
    print(f"Failures: {len(composition.failures)}")

    for i, fail in enumerate(composition.failures):
        print(f"  {i+1}. {fail.failure_type}")
```

### Get Failure Result

```python
if fail_guard.has_failures():
    failure_result = fail_guard.get_failure_result()
    print(f"Terminal: {failure_result.terminal}")
    print(f"Failures: {len(failure_result.failures)}")
```

## Failure Event Structure

```python
@dataclass(frozen=True)
class FailureEvent:
    failure_id: str                    # Unique identifier
    phase: Phase                        # MEK phase
    failure_type: FailureType           # Type of failure (enum)
    triggering_condition: str           # Exact condition
    timestamp: int                       # Monotonic timestamp
    step_id: Optional[str]              # Step ID (for compositions)
    violated_invariant: Optional[Invariant] # Violated invariant
    authority_context: Optional[dict]    # Principal, grant IDs
    snapshot_id: Optional[str]           # Snapshot ID
```

## Failure Composition Rules

- **Preserves order of occurrence** - failures in timestamp order
- **No deduplication** - each failure is preserved
- **No summarization** - no merging or collapsing
- **No "root cause" inference** - no primary/secondary classification
- **No severity ranking** - no critical/major/minor fields
- **No collapsing** - each failure is separate

## Failure Result Structure

```python
@dataclass(frozen=True)
class FailureResult:
    composition_id: Optional[str]   # Composition ID
    failures: List[FailureEvent]    # Ordered failures
    terminal: bool = True           # Always True
```

**No success metadata allowed.**

## Failure Types

Closed enum - no new types allowed:

**Context Failures:**
- MISSING_CONTEXT
- INVALID_CONTEXT
- CONTEXT_IMMUTABILITY_VIOLATION

**Intent Failures:**
- MISSING_INTENT
- INVALID_INTENT
- INTENT_INFERENCE_ATTEMPT

**Confidence Failures:**
- MISSING_CONFIDENCE
- INVALID_CONFIDENCE
- CONFIDENCE_THRESHOLD_EXCEEDED

**Principal Failures:**
- MISSING_PRINCIPAL
- UNKNOWN_PRINCIPAL

**Grant Failures:**
- MISSING_GRANT
- EXPIRED_GRANT
- REVOKED_GRANT
- EXHAUSTED_GRANT
- INVALID_GRANT_SCOPE

**Capability Failures:**
- UNKNOWN_CAPABILITY
- CAPABILITY_SELF_INVOCATION

**Authority Failures:**
- UNIFIED_EXECUTION_AUTHORITY_VIOLATION
- DIRECT_EXECUTION_ATTEMPT

**Friction Failures:**
- FRICTION_VIOLATION
- CONSEQUENCE_LEVEL_MISMATCH

**Snapshot Failures:**
- SNAPSHOT_HASH_MISMATCH
- SNAPSHOT_REUSE_ATTEMPT
- TOCTOU_VIOLATION

**Composition Failures:**
- COMPOSITION_STEP_FAILURE
- COMPOSITION_ORDER_VIOLATION

**Execution Failures:**
- EXECUTION_ERROR
- GUARD_REFUSAL

## Running Tests

```bash
cd mek5
python -m pytest tests.py -v
```

All 20 tests MUST pass:
- 4 failure event creation tests
- 5 failure composition tests
- 4 failure result tests
- 3 failure guard integration tests
- 1 observer non-authority test
- 3 failure immutability tests

## Running Example

```bash
cd mek5
python example.py
```

## Statistics

- **Total LOC**: ~1,434
- **Total Tests**: 20
- **Files**: 7

## Dependencies

- `pytest>=8.0.0` - Test framework

**Depends on:**
- `mek0.kernel` (MEK-0 Guard)
- `mek2.authority_guard` (MEK-2 AuthorityGuard)
- `mek3.snapshot_guard` (MEK-3 SnapshotAuthorityGuard)
- `mek4.composition_guard` (MEK-4 CompositionGuard)

## Absolute Prohibitions

MEK-5 MUST NOT:

- Convert failures into advice
- Merge similar failures
- Reduce failure count
- Explain "why this happened"
- Provide next steps
- Optimize presentation
- Suggest fixes
- Recommend workarounds

**Failure is evidence, not guidance.**

## Core Principle

**Failure Event → Failure Composition → Failure Result**

Failure is data, not UX.
Failure is evidence, not guidance.

**The system fails honestly and stops.**

---

**Failure is data, not UX. The system fails honestly and stops.**
