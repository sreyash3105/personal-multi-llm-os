# AIOS VISION-ALIGNED UPGRADE PATH

## Version: 1.0
## Status: CODE-ORIENTED ROADMAP (NO IMPLEMENTATION)

---

## OVERVIEW

This document outlines the evolution path for AIOS from its current local-first state to a vision-aligned architecture. The design prioritizes:

- **Truth-first** over estimation
- **Explicit refusal** over silent guessing
- **Intentional slowness** for risky operations
- **Visibility of misuse** without silent intervention
- **Local-first core** with adapters as later additions

---

## PRINCIPLES

### 1. Truth-First Design
- System must report what it knows, not what it guesses
- Uncertainty must be explicit, not hidden behind estimates
- All actions must be traceable to their source truth

### 2. Refusal Over Guessing
- When uncertain, the system MUST refuse rather than guess
- Refusal must include explicit reason and suggested alternatives
- No "best effort" fallbacks that hide uncertainty

### 3. Slowness Under Consequence
- Risky operations MUST impose deliberate delay (friction)
- High-confidence actions proceed normally
- Low-confidence actions trigger confirmation delays

### 4. Visibility Without Intervention
- Misuse patterns must be recorded, not blocked
- Pattern aggregation remains non-blocking
- All refusals are logged with full context

### 5. Local-First Core
- Core logic never assumes remote execution
- All adapters are explicit and opt-in
- No hidden network calls in core modules

---

## CURRENT STATE (BASELINE)

### Completed (Accepted as Truth)
```
✓ FastAPI / HTTP layer removed
✓ Local runner and context manager implemented
✓ Pure function execution paths
✓ Pattern aggregation functional
✓ Security permissions system operational
✓ Confirmation flow operational
✓ STT/TTS services local
✓ All imports resolve correctly
✓ Tests pass for local execution
```

### Current Capabilities
- Code generation, review, judgment
- Study mode
- Vision analysis
- Tools execution
- Chat (normal and smart modes)
- Automation planning and execution
- Security sessions and permissions
- Pattern detection and reporting

---

## UPGRADE PHASES

### PHASE 1: TRUTH-ENFORCEMENT

#### 1.1 Uncertainty Reporting
**Status:** NOT STARTED

**Requirement:** All model outputs MUST include confidence metadata

**Changes Required:**
- Modify `backend/modules/code/pipeline.py` to return:
  ```python
  {
    "output": str,
    "confidence": float,           # 0.0 to 1.0
    "reasoning": str,            # Why this output
    "alternatives": List[str],     # What else was considered
  }
  ```
- Modify `backend/modules/vision/vision_pipeline.py` to return:
  ```python
  {
    "output": str,
    "confidence": float,
    "detection_bounds": {          # What was actually detected
      "coordinates": (int, int),
      "uncertainty_radius": int,
    },
    "suggested_reframing": str,    # Better prompt if low confidence
  }
  ```

**Acceptance:**
- All pipeline functions return structured outputs with confidence
- No raw string-only returns remain
- Confidence is always explicit, never inferred

#### 1.2 Refusal Protocol
**Status:** NOT STARTED

**Requirement:** Explicit refusal must replace silent failure

**Changes Required:**
- Create `backend/core/refusal.py`:
  ```python
  class RefusalReason(Enum):
    UNCERTAIN = "uncertain"
    OUT_OF_SCOPE = "out_of_scope"
    RISK_THRESHOLD = "risk_threshold"
    MISSING_CONTEXT = "missing_context"
    CONFLICT = "conflict"

  def create_refusal(
    reason: RefusalReason,
    explanation: str,
    alternatives: List[str],
    source_confidence: float
  ) -> dict:
    """Create structured refusal response."""
    return {
      "status": "refused",
      "reason": reason,
      "explanation": explanation,
      "alternatives": alternatives,
      "source_confidence": source_confidence,
    }
  ```

**Acceptance:**
- All modules use `create_refusal()` for uncertain operations
- No silent None/empty returns
- Every refusal has actionable alternatives

#### 1.3 Truth-Preserved Logging
**Status:** NOT STARTED

**Requirement:** Log what was asked, what was known, and what was done

**Changes Required:**
- Extend history logging schema:
  ```python
  {
    "mode": str,
    "original_prompt": str,
    "known_truth": {
      "what_was_known": str,
      "certainty": float,
      "source": str,
    },
    "decision": {
      "action": str,
      "rationale": str,
    },
    "outcome": str,
  }
  ```

**Acceptance:**
- All history records include known_truth field
- Rationale is always explicit
- No "AI decided" without documented reasoning

---

### PHASE 2: FRICTION & CONSEQUENCE

#### 2.1 Deliberate Delay Mechanism
**Status:** NOT STARTED

**Requirement:** Risky operations impose observable delay

**Changes Required:**
- Create `backend/core/friction.py`:
  ```python
  def apply_friction(
    risk_level: int,  # 1-10 scale
    callback: Callable,
    max_delay_seconds: int = 30
  ) -> Any:
    """Execute callback with delay based on risk level."""
    import time
    delay = risk_level * 2.0  # 2 seconds per risk level
    delay = min(delay, max_delay_seconds)
    print(f"[FRICTION] Delaying {delay}s for risk_level={risk_level}")
    time.sleep(delay)
    return callback()
  ```

**Acceptance:**
- All tool executions wrap with `apply_friction()`
- Risk level 1: 2s delay
- Risk level 10: 30s delay
- User cannot bypass friction (except via explicit flag)

#### 2.2 Confirmation Gate Strengthening
**Status:** NOT STARTED

**Requirement:** Low-confidence actions require explicit human confirmation

**Changes Required:**
- Enhance `backend/core/confirmation.py` with:
  ```python
  def requires_confirmation(
    confidence: float,
    threshold: float = 0.6,
    action_type: str = "unknown"
  ) -> bool:
    """Determine if action requires confirmation."""
    return confidence < threshold

  def present_confirmation(
    action: str,
    confidence: float,
    metadata: dict
  ) -> bool:
    """Block execution until user confirms."""
    print(f"\n{'='*60}")
    print(f"CONFIRMATION REQUIRED")
    print(f"{'='*60}")
    print(f"Action: {action}")
    print(f"Confidence: {confidence:.2f}")
    print(f"Metadata: {metadata}")
    print(f"\nPress ENTER to confirm, Ctrl+C to cancel...")
    print(f"{'='*60}\n")
    input()  # Block for user input
    return True
  ```

**Acceptance:**
- Actions below 0.6 confidence always confirm
- User must explicitly acknowledge
- Confirmation timeout causes automatic cancellation

---

### PHASE 3: VISIBILITY & PATTERN DETECTION

#### 3.1 Misuse Pattern Detection (No Blocking)
**Status:** PARTIAL - Pattern aggregation exists, needs enhancement

**Requirement:** Detect but DO NOT block misuse patterns

**Changes Required:**
- Enhance `backend/core/pattern_aggregator.py` with new pattern types:
  ```python
  class PatternType(Enum):
    # Existing
    IDENTICAL_REFUSAL_BYPASS = "identical_refusal_bypass"
    IMMEDIATE_CONFIRM_AFTER_FRICTION = "immediate_confirm_after_friction"
    REPEATED_LOW_CONFIDENCE = "repeated_low_confidence"

    # New patterns
    PROMPT_INJECTION_ATTEMPT = "prompt_injection_attempt"
    PRIVILEGE_ESCALATION_PROBE = "privilege_escalation_probe"
    LOOP_AVOIDANCE_CHECK = "loop_avoidance_check"
    OBSCURITY_BYPASS_ATTEMPT = "obscurity_bypass_attempt"
  ```

**Acceptance:**
- All patterns are recorded in `pattern_events` table
- No pattern execution blocks operations
- Pattern detection is read-only (observability only)

#### 3.2 Pattern Reporting
**Status:** PARTIAL - Reporting exists, needs UI exposure

**Requirement:** Make patterns visible without intervention

**Changes Required:**
- Add to `backend/core/local_runner.py`:
  ```python
  def list_patterns(
    profile_id: str,
    pattern_type: Optional[str] = None,
    limit: int = 100
  ) -> List[dict]:
    """Query pattern events for visibility."""
    from backend.core.pattern_aggregator import PatternAggregator
    agg = PatternAggregator()
    return agg.query_patterns(profile_id, pattern_type, limit)

  def generate_pattern_report(
    profile_id: str,
    hours: int = 24
  ) -> str:
    """Generate human-readable pattern report."""
    from backend.core.pattern_report import generate_text_report
    return generate_text_report(profile_id, hours=hours)
  ```

**Acceptance:**
- Users can query their pattern history
- Reports are human-readable
- No automatic action taken on patterns

---

### PHASE 4: LOCAL-FIRST CORE ISOLATION

#### 4.1 Core Module Audit
**Status:** NOT STARTED

**Requirement:** Ensure no module assumes HTTP or remote execution

**Changes Required:**
- Audit all imports for HTTP libraries
  ```bash
  # Must be zero matches
  grep -rn "requests\.get\|httpx\|aiohttp" backend --include="*.py"
  ```
- Ensure all `subprocess` calls are explicit
  ```python
  # Good
  subprocess.run(["ollama", "run", ...], check=True)

  # Bad (hidden HTTP)
  subprocess.run(["curl", ...])
  ```

**Acceptance:**
- No HTTP libraries in core logic
- All external calls are via explicit adapters
- No implicit network dependencies

#### 4.2 Adapter Boundary Definition
**Status:** NOT STARTED

**Requirement:** Explicitly define where adapters will be added

**Changes Required:**
- Create `backend/core/adapters.py` (skeleton only):
  ```python
  """
  Adapter boundary - defines where external integrations will occur.

  Adapters are OPT-IN, not part of core execution.
  Core remains local and HTTP-free.
  """

  # Future adapters (NOT IMPLEMENTED):
  # - HTTPAdapter: For remote execution servers
  # - WebSocketAdapter: For real-time streaming
  # - CLIVerbsAdapter: For command-line integration
  # - DesktopAdapter: For native UI integration

  class AdapterInterface:
    """All adapters must implement this interface."""
    def execute(self, request: dict) -> dict:
        raise NotImplementedError

  class NoAdapter(AdapterInterface):
    """Default adapter for local-only execution."""
    def execute(self, request: dict) -> dict:
        # Use local runner
        from backend.core.local_runner import get_runner
        return get_runner().execute_code(request.get("prompt", ""))
  ```

**Acceptance:**
- Adapter interface defined
- Core has NoAdapter by default
- No adapters implemented (per specification)

---

## FORBIDDEN MODIFICATIONS

The following are **NOT ALLOWED** during upgrade:

### 1. Autonomous Behavior
- No self-initiated operations
- No background tasks without explicit trigger
- No scheduled actions

### 2. Fallback Logic
- No "best effort" that hides refusal
- No silent retry without logging
- No "I'll try my best" behavior

### 3. Learning or Adaptation
- No model tuning or training
- No prompt optimization storage
- No pattern-based prompt adjustment

### 4. Optimization for UX
- No reducing friction for "better experience"
- No speeding up risky operations
- No reducing confirmation requirements
- No hiding uncertainty behind "helpful" messages

### 5. "Helper Intelligence"
- No guessing what user "really meant"
- No expanding ambiguous requests
- No auto-correcting "mistakes"
- No second-guessing refusals

---

## NEW MODULES REQUIRED

### Core Modules (MUST IMPLEMENT)
1. `backend/core/refusal.py` - Explicit refusal protocol
2. `backend/core/friction.py` - Deliberate delay mechanism
3. `backend/core/adapters.py` - Adapter interface definition

### Enhanced Existing Modules
1. `backend/modules/code/pipeline.py` - Add confidence output
2. `backend/modules/vision/vision_pipeline.py` - Add detection bounds
3. `backend/core/confirmation.py` - Strengthen confirmation gate
4. `backend/core/pattern_aggregator.py` - Add new pattern types

---

## NEW DEPENDENCIES REQUIRED

None. All upgrades use existing dependencies:
- No new external libraries
- No AI/ML framework additions
- No network libraries

---

## EXECUTION ORDER

1. **Phase 1.1** - Uncertainty reporting in code/vision pipelines
2. **Phase 1.2** - Refusal protocol implementation
3. **Phase 1.3** - Truth-preserved logging schema
4. **Phase 2.1** - Deliberate delay mechanism
5. **Phase 2.2** - Confirmation gate strengthening
6. **Phase 3.1** - New pattern type detection (non-blocking)
7. **Phase 3.2** - Pattern reporting exposure
8. **Phase 4.1** - Core module audit and cleanup
9. **Phase 4.2** - Adapter boundary definition

Each phase must:
- Pass existing tests
- Add new tests for new functionality
- Not modify existing behavior unless explicitly specified
- Not introduce new capabilities beyond scope

---

## ACCEPTANCE CRITERIA

This upgrade path is complete when:

- [ ] All pipelines return structured outputs with confidence
- [ ] Explicit refusal protocol is defined and used
- [ ] Friction mechanism imposes delays based on risk
- [ ] Confirmation gates require explicit user acknowledgment
- [ ] Pattern detection includes new types (non-blocking)
- [ ] Pattern reporting is visible to users
- [ ] Core is audited and confirmed local-only
- [ ] Adapter interface is defined (no implementations)
- [ ] No forbidden modifications are present
- [ ] All tests pass with new structure
- [ ] Documentation exists in `/docs/evolution/`

---

## NOTES

- This is a **roadmap artifact**, not implementation code
- No code should be written without explicit phase trigger
- All changes maintain the principle: **truth, not convenience**
- Refusal is a feature, not a bug
- Slowness is intentional, not performance issue
