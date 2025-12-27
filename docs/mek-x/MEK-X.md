# MEK-X: SANDBOXED INTELLIGENCE ZONE

## Core Principle

MEK-X has **zero authority**.

MEK-X may:
- Think
- Plan
- Reason
- Simulate
- Generate hypotheses
- Store memory
- Suggest proposals

MEK-X may **NEVER**:
- Execute actions
- Grant authority
- Influence MEK decisions
- Bypass Guard
- Modify evidence or failure records

## Architecture

### Components

- **proposal.py**: Proposal data structure (output only)
- **intelligence.py**: Intelligence engine (planning, reasoning, simulation)
- **sandbox.py**: Isolation enforcement (import hooks)

### Isolation

- Separate package namespace (`backend/mek_x/`)
- No imports from MEK core
- No access to Guard, capability registry, snapshot store
- No shared globals

### Interface

MEK-X → MEK: **Proposal only**

```python
{
    "proposal_id": "uuid",
    "text": "opaque text",
    "assumptions": ["list"],
    "confidence_range": "MEDIUM",
    "known_unknowns": ["list"],
    "requested_actions": [{"type": "symbolic"}]
}
```

## Capabilities

### Planning
- Generate plans for goals
- Consider constraints
- Return proposal only

### Reasoning
- Answer questions
- Analyze context
- Return proposal only

### Hypothesis Generation
- Generate testable hypotheses
- Identify evidence
- Store in MEK-X memory only

### Simulation
- Simulate scenarios
- Run iterations
- Return proposal only

### Memory
- Store long-term state
- Retrieve by key
- Stored in MEK-X space only

### Retries & Optimization
- Generate optimized proposals
- Apply heuristics
- Return proposal only

## Non-Goals

- No execution
- No authority granting
- No Guard influence
- No snapshot emission
- No failure emission
- No evidence bundle emission
- No MEK state modification
