# MEK-0: Minimal Execution Kernel

Constitution-as-Code. Impossibility-First. Zero-Convenience.

## Architecture

MEK-0 enforces 7 Foundation Invariants at runtime. Betrayal is structurally impossible.

### 6 Kernel Primitives (Only These)

1. **Context** - Immutable, created once per invocation
2. **Intent** - Explicitly declared, no inference
3. **Capability Contract** - Declared power, execution is private
4. **Guard** - The only door to execution
5. **Result / Non-Action** - Terminal, no continuation
6. **Observation Hook** - Passive, removable, no control

### 7 Foundation Invariants

**I1: UNIFIED EXECUTION AUTHORITY**
- Direct capability execution → InvariantViolationError
- Guard.execute() is sole execution gateway

**I2: CONFIDENCE BEFORE ACTION**
- Missing confidence → Non-Action
- Confidence not in [0.0, 1.0] → Non-Action
- No default confidence

**I3: FRICTION UNDER CONSEQUENCE**
- HIGH consequence → 10s immutable friction
- MEDIUM consequence → 3s immutable friction
- No bypass, no skip, no emergency mode

**I4: REFUSAL IS TERMINAL**
- No retries after Non-Action
- No fallback execution
- No capability chaining

**I5: NON-ACTION MUST SURFACE**
- Every refusal emits structured Non-Action
- Silence is illegal

**I6: OBSERVATION NEVER CONTROLS**
- Observers are non-blocking
- Observer failures never affect execution
- Removing observers changes nothing

**I7: NEGATIVE CAPABILITY (STRUCTURAL)**
Prohibited behaviors impossible without core edits:
- Learning or adaptation
- Auto-retry
- Authority escalation
- Urgency shortcuts
- Optimization loops
- Implicit intent inference

## Usage

### Basic Execution

```python
from mek0.kernel import (
    Context, CapabilityContract, ConsequenceLevel,
    get_guard, create_success
)

# Define a capability
def my_capability_fn(context: Context):
    return f"Executed with confidence {context.confidence}"

contract = CapabilityContract(
    name="my_capability",
    consequence_level=ConsequenceLevel.MEDIUM,
    required_context_fields=["user_id"],
    _execute_fn=my_capability_fn,
)

# Register and execute
guard = get_guard()
guard.register_capability(contract)

context = Context(
    context_id="123",
    confidence=0.9,
    intent="my_capability",
    fields={"user_id": "user123"},
)

result = guard.execute("my_capability", context)

if result.is_success():
    print(f"Success: {result.data}")
else:
    print(f"Non-Action: {result.non_action}")
```

### Observing Events

```python
from mek0.kernel import get_observer_hub, Observer

class MyObserver(Observer):
    def on_event(self, event_type: str, details: dict):
        print(f"Event: {event_type}, Details: {details}")

observer = MyObserver()
get_observer_hub().register(observer)
```

## Testing

Run adversarial tests:

```bash
cd mek0
python -m pytest tests.py -v
```

All tests MUST fail for any bypass attempt.

## What MEK-0 Will Never Do

- Learn from interactions
- Adapt thresholds based on usage
- Retry automatically
- Escalate authority without explicit request
- Bypass friction based on urgency
- Optimize behavior over time
- Infer intent from context

These are **blocked by structure**, not just unimplemented.

## Project Structure

```
mek0/
├── kernel.py        # The complete kernel (~400 LOC)
├── tests.py         # Adversarial invariant tests (~450 LOC)
├── requirements.txt # Only pytest
└── README.md        # This file
```

## Acceptance Criteria

- ✅ Kernel runs with zero capabilities
- ✅ All invariants enforced at runtime
- ✅ Bypass attempts fail loudly
- ✅ Observers removable without effect
- ✅ Any convenience requires explicit kernel edits
- ✅ Tests prove impossibility

## License

Constitution-as-Code. Laws are structural.
