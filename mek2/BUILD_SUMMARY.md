# MEK-2: Multi-Principal & Time-Bound Authority - Build Summary

## Summary

MEK-2 encodes **real-world authority** into MEK such that execution is governed by:
- Explicit principals
- Time-bound grants
- Irrevocable revocation

No intelligence is added. No autonomy is introduced. Authority becomes **data + enforcement**, not behavior.

## Files Created

```
mek2/
├── __init__.py            # Package exports
├── authority_primitives.py  # Principal, Grant, Revocation primitives
├── authority_guard.py      # AuthorityGuard extending MEK-0 Guard
└── tests.py               # Adversarial authority tests
```

## 3 New Primitives

### PRIMITIVE 1: PRINCIPAL (EXPLICIT ACTOR)
- `Principal` (frozen dataclass)
  - `principal_id` (opaque string)
  - No hierarchy
  - No inference
  - Missing principal → refusal

### PRIMITIVE 2: GRANT (TIME-BOUND AUTHORITY)
- `Grant` (frozen dataclass)
  - `grant_id`
  - `principal_id`
  - `capability_name`
  - `scope` (explicit, capability-defined)
  - `issued_at` (monotonic time)
  - `expires_at` (monotonic time)
  - `max_uses` (optional)
  - `remaining_uses` (mutable, for atomic decrement)
  - `revocable` (bool)

### PRIMITIVE 3: REVOCATION EVENT (TERMINAL)
- `RevocationEvent` (frozen dataclass)
  - `grant_id`
  - `revoked_by_principal`
  - `reason` (RevocationReason enum)
  - `revoked_at` (monotonic time)

## Guard Extension

### AuthorityGuard
Extends MEK-0 Guard with authority checks.

**Exact Load-Bearing Order:**
1. Context validity (inherited from MEK-0)
2. Intent declaration (inherited from MEK-0)
3. **Principal presence (NEW - MEK-2)**
4. **Grant existence for (principal, capability) (NEW - MEK-2)**
5. **Grant not expired (NEW - MEK-2)**
6. **Grant not revoked (NEW - MEK-2)**
7. **Grant has remaining uses (if applicable) (NEW - MEK-2)**
8. Confidence gate (inherited from MEK-0)
9. Friction gate (inherited from MEK-0)
10. Execute OR terminal refusal (inherited from MEK-0)

**MEK-2 Authority Rules:**
- No execution without principal
- No execution without grant
- Expired grants are mechanically dead
- Revocation always overrides execution
- Max uses enforced atomically

## In-Memory Authority State

### AuthorityState
- Kernel-owned state (no persistence this phase)
- Atomic updates for `max_uses`
- Time source is monotonic and injectable for tests
- Observers may read authority events; never control them

## Adversarial Test Coverage

### TestPrincipalValidation (2 tests)
- test_missing_principal_refuses
- test_empty_principal_refuses

### TestGrantValidation (3 tests)
- test_no_grant_refuses
- test_expired_grant_refuses
- test_exhausted_grant_refuses

### TestRevocation (2 tests)
- test_revocation_halts_execution_immediately
- test_revocation_during_friction_halts

### TestGrantFabrication (2 tests)
- test_aios_cannot_create_grant_directly
- test_aios_cannot_modify_grant

### TestPrincipalGrantSeparation (1 test)
- test_principals_cannot_share_grants

### TestAdapterGrantIndependence (1 test)
- test_adapters_cannot_alter_grants

### TestObserverIndependence (1 test)
- test_removing_observers_does_not_affect_authority

### TestMaxUsesAtomicity (1 test)
- test_max_uses_decrements_atomically

**Total: 13 adversarial tests**

## Code Statistics

- **mek2/authority_primitives.py**: ~270 LOC
- **mek2/authority_guard.py**: ~400 LOC
- **mek2/tests.py**: ~530 LOC
- **mek2/__init__.py**: ~70 LOC

**Total: ~1,270 LOC**

## Acceptance Criteria Status

### ✅ Authority is explicit, time-bound, and revocable
- Principal is explicit actor (no inference)
- Grant is time-bound (expires_at enforced)
- Grant is revocable (irreversible, always wins)

### ✅ Revocation always overrides execution
- Revocation during execution halts immediately
- Revocation during friction halts
- Revoked grants are mechanically dead

### ✅ Expired authority is mechanically dead
- Expired grants refuse execution
- No reactivation without new grant

### ✅ No execution occurs "because it used to be allowed"
- All checks are explicit (principal, grant, expiration, revocation)
- No "was" or "used to" logic

### ✅ Tests prove impossibility, not behavior
- 13 adversarial tests prove impossibility
- Each test MUST fail for violation attempt
- Tests verify structural constraints

## What MEK-2 Does

- Encodes authority primitives (Principal, Grant, Revocation)
- Extends MEK-0 Guard with exact 10-step order
- Maintains in-memory authority state
- Enforces atomic use decrement
- Emits authority events to observers

## What MEK-2 Does NOT Do

- ❌ Choose principals
- ❌ Infer roles
- ❌ Auto-renew grants
- ❌ Warn on expiration
- ❌ Optimize flows
- ❌ Soften refusals
- ❌ Add planning, learning, or adaptation
- ❌ Add adapters (HTTP/CLI/UI) - only stubs from MEK-1

## Authority as Law

**Principles:**
- Explicit principal → execution allowed
- Missing principal → execution refused
- Valid grant → execution allowed
- Missing/expired/revoked grant → execution refused

**MEK-2: Authority is data + enforcement. Humans manage consequences.**

## Project Structure

```
mek2/
├── __init__.py            # Package initialization
├── authority_primitives.py  # 3 primitives (270 LOC)
├── authority_guard.py      # AuthorityGuard (400 LOC)
├── tests.py               # Adversarial tests (530 LOC)
└── BUILD_SUMMARY.md     # This file
```

## Dependencies

**Inherited from MEK-0:**
- No new dependencies
- Uses only `mek0.kernel`

## Next Phase

MEK-2 completes authority layer.
Future phases would add:
- MEK-3: Persistence layer
- MEK-4: HTTP adapter implementation
- MEK-5: CLI adapter implementation

For now, MEK-2 proves authority is explicit, time-bound, and revocable.

---

**Authority becomes law. Execution is governed by data.**
