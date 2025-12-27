# MEK-4: Composition Without Power

**Mechanical composition without emergent authority. MEK composes actions, not meaning.**

## Overview

MEK-4 enables multi-step execution of capabilities without creating new authority, intent, or power.

Composition is:
- **Mechanical** - no planning, no reasoning
- **Explicit** - no inference, no defaults
- **Non-aggregating** - each step is independent
- **Non-escalating** - no emergent authority

## Philosophy

**Composition is NOT planning.**

Composition IS:
- Mechanical sequencing of independent steps
- Each step passes through Guard independently
- STRICT failure policy (first refusal halts everything)

Composition is NOT:
- Planning or reasoning
- Intent inference across steps
- Grant merging or extension
- Partial success masking
- Emergent authority

## Files

```
mek4/
├── __init__.py                 # Package exports
├── composition_primitives.py    # Composition primitives
├── composition_guard.py         # Guard integration
├── tests.py                    # Adversarial tests (15 tests)
├── requirements.txt             # Dependencies
├── BUILD_SUMMARY.md            # Implementation summary
└── example.py                  # Usage examples
```

## Usage

### Create a Composition

```python
from composition_primitives import create_composition

composition = create_composition(
    composition_id="comp_001",
    steps=[
        {
            "step_id": "read_config",
            "capability_name": "file_read",
            "context": {
                "principal_id": "user123",
                "confidence": 0.9,
                "path": "/etc/config.txt",
            },
            "order": 0,
        },
        {
            "step_id": "write_backup",
            "capability_name": "file_write",
            "context": {
                "principal_id": "user123",
                "confidence": 0.9,
                "path": "/tmp/config.bak",
            },
            "order": 1,
        },
    ],
)
```

### Execute Composition

```python
from composition_guard import get_composition_guard

# Get composition guard with MEK Guard
guard = get_mek_guard()  # From MEK-3
comp_guard = get_composition_guard(guard)

# Execute composition
result = comp_guard.execute_composition(composition)

if result.is_success:
    print(f"Success: {result.final_data}")
else:
    print(f"Refused at step: {result.halted_at_step}")
    print(f"Reason: {result.non_action.get('reason')}")
```

## Composition Rules

- Each step has **independent Context**
- Each step has **independent Intent**
- Each step has **independent Snapshot**
- Each step passes **independently through Guard**
- **STRICT failure policy**: first refusal halts entire composition
- **No partial success exposure**
- **No retries**
- **No branching**
- **No conditional logic**

## Step Independence

Each step:
- Has its own Context
- Has its own Intent (capability)
- Has its own Snapshot
- Passes through Guard independently

**No shared authority. No shared snapshot. No shared power.**

## STRICT Failure Policy

- First refusal halts entire composition
- No retries
- No alternative policies
- No partial success exposure

## Running Tests

```bash
cd mek4
python -m pytest tests.py -v
```

All 15 tests MUST pass:
- 3 composition creation tests
- 4 step execution independence tests
- 3 failure policy strictness tests
- 1 observer non-authority test
- 2 composition immutable law tests
- 2 composition result semantics tests

## Running Example

```bash
cd mek4
python example.py
```

## Statistics

- **Total LOC**: ~1,367
- **Total Tests**: 15
- **Files**: 7

## Dependencies

- `pytest>=8.0.0` - Test framework

**Depends on:**
- `mek0.kernel` (MEK-0 Guard)
- `mek2.authority_guard` (MEK-2 AuthorityGuard)
- `mek3.snapshot_guard` (MEK-3 SnapshotAuthorityGuard)

## Absolute Prohibitions

Composition MUST NOT:

- Infer new intent from prior steps
- Reuse grants across steps implicitly
- Allow one grant to "cover" multiple steps
- Downgrade consequence levels
- Reduce friction due to prior waits
- Justify later execution because earlier succeeded

## Core Principle

**Step 1 → Guard → Result/Refusal**
**Step 2 → Guard → Result/Refusal**
**Step 3 → Guard → Result/Refusal**

Each step is independent.
No shared authority. No shared snapshot. No shared power.

---

**MEK composes actions, not meaning.**
