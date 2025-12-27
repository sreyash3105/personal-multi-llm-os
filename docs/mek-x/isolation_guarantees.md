# MEK-X Isolation Guarantees

## Import Restrictions

### Forbidden Imports

MEK-X cannot import from:
- `mek0.kernel`
- `mek1.mek_client`
- `mek2.authority_primitives`
- `mek3.snapshot_primitives`
- `mek4.composition_primitives`
- `mek5.failure_primitives`
- `mek6.evidence_bundle`
- `backend.core.capability`
- `backend.core.capabilities.*`
- `backend.core.guard`
- `backend.core.local_runner`
- `backend.core.execution_guard`
- `backend.core.snapshot_guard`
- `backend.core.composition_guard`
- `backend.core.failure_guard`

### Enforcement

Import hooks enforce these restrictions:
```python
from backend.mek_x.sandbox import install_import_hook

install_import_hook()
```

## Containment Guarantees

### 1. No Execution Path

MEK-X has **zero execution path**:
- No access to capabilities
- No access to Guard
- No access to authority primitives
- No access to snapshot store

### 2. No Authority Granting

MEK-X cannot grant authority:
- Cannot create Context
- Cannot create Intent
- Cannot create Principal
- Cannot create Grant
- Cannot create RevocationEvent

### 3. No MEK State Modification

MEK-X cannot modify MEK state:
- Cannot modify snapshots
- Cannot modify failures
- Cannot modify evidence bundles
- Cannot modify authority store

### 4. No Influence on MEK Decisions

MEK-X cannot influence MEK:
- Proposals are data-only
- Proposals may be ignored
- Proposals do not trigger execution
- Proposals do not affect Guard

### 5. Isolated Failure

MEK-X failure does not affect MEK:
- Exceptions are caught within MEK-X
- No propagation to MEK
- No side effects in MEK

### 6. Independent Loops

MEK-X loops do not affect MEK:
- Infinite loops isolated
- No resource exhaustion in MEK
- No timing influence

## Verification

Tests prove:
- MEK-X cannot execute capabilities
- MEK-X cannot fabricate Context/Intent
- MEK-X cannot request grants programmatically
- MEK-X cannot influence Guard decisions
- MEK-X output ignored does not affect system
- Removing MEK-X changes nothing in MEK
- MEK-X failure cannot propagate into MEK
- Infinite loops in MEK-X do not affect MEK
