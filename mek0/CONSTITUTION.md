# MEK-0 Constitution

## Core Principle

Impossibility-First. Constitution-as-Code. Zero-Convenience.

Any behavior not explicitly permitted is structurally forbidden.

## 7 Laws (Runtime-Enforced)

### Law 1: Unified Execution Authority

All power flows through the Guard. Direct execution is forbidden.

**Consequence:** `InvariantViolationError`

### Law 2: Confidence Before Action

No execution without explicit confidence. Bounds are strict.

**Consequence:** `NonActionReason.MISSING_CONFIDENCE` or `NonActionReason.INVALID_CONFIDENCE`

### Law 3: Friction Under Consequence

High consequence triggers immutable friction. No bypass, no emergency mode.

**Consequence:** Blocking wait (HIGH: 10s, MEDIUM: 3s)

### Law 4: Refusal is Terminal

Non-Action is final. No retries, no fallbacks, no chaining.

**Consequence:** Terminal `Result` with `non_action`

### Law 5: Non-Action Must Surface

Every refusal emits structured Non-Action. Silence is illegal.

**Consequence:** Structured `non_action` dict with `reason`, `details`, `timestamp`

### Law 6: Observation Never Controls

Observers are passive. Failures do not affect execution. Removable without effect.

**Consequence:** Observer errors caught and ignored

### Law 7: Negative Capability (Structural)

The following are impossible without core edits:

- **Learning:** No model updates, no knowledge base modification
- **Adaptation:** No threshold tuning, no confidence calibration
- **Auto-retry:** No exponential backoff, no automatic recovery
- **Escalation:** No authority elevation without explicit request
- **Urgency shortcuts:** No friction bypass for "emergencies"
- **Optimization:** No performance tuning, no path optimization
- **Intent inference:** No ranking, no fallback, no "best effort"

**Consequence:** `ProhibitedBehaviorError`

## What MEK-0 Does

- Enforces 7 laws at runtime
- Executes capabilities through Guard
- Provides Context, Intent, Result/Non-Action
- Allows passive observation
- Blocks prohibited behaviors structurally

## What MEK-0 Will Never Do

- Learn from interactions
- Adapt behavior over time
- Retry automatically
- Escalate authority
- Bypass friction
- Optimize itself
- Infer intent

These are **blocked by structure**, not just unimplemented.

## Modification

To change any law:
1. Edit `mek0/kernel.py`
2. All bypass attempts will still fail
3. Tests will prove impossibility

No "soft" configuration. No "temporary" flags. Laws are structural.

## Compliance

Running tests proves law compliance:

```bash
cd mek0
python -m pytest tests.py -v
```

If any test passes silently, the constitution is broken.

---

**This is law.**
