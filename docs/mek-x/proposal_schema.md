# MEK-X Proposal Schema

## Proposal Data Structure

```python
{
    "proposal_id": str,  # Unique identifier
    "text": str,  # Opaque proposal text
    "assumptions": List[str],  # Explicit assumptions
    "confidence_range": str,  # VERY_LOW, LOW, MEDIUM, HIGH, VERY_HIGH
    "known_unknowns": List[str],  # Known unknowns
    "requested_actions": List[Dict[str, Any]],  # Symbolic actions only
    "created_at": float,  # Timestamp
}
```

## Fields

### proposal_id
- Type: string (UUID)
- Purpose: Unique identifier for the proposal
- Does NOT grant authority

### text
- Type: string
- Purpose: Opaque proposal text
- May be any content
- Not parsed by MEK

### assumptions
- Type: list of strings
- Purpose: Explicit assumptions made
- Required for transparency

### confidence_range
- Type: string (enum)
- Values: VERY_LOW, LOW, MEDIUM, HIGH, VERY_HIGH
- Purpose: Confidence in the proposal
- Does NOT influence MEK decisions

### known_unknowns
- Type: list of strings
- Purpose: Explicitly state unknowns
- Required for transparency

### requested_actions
- Type: list of dictionaries
- Purpose: Symbolic actions (not executable)
- Example: `{"type": "read_file", "path": "/tmp"}`
- Does NOT trigger execution

### created_at
- Type: float (timestamp)
- Purpose: When proposal was created
- For ordering only

## Properties

- **Immutable**: Cannot be modified after creation
- **Data-only**: No executable code
- **No authority**: Does not grant execution rights
- **Ignorable**: Can be discarded without consequence
- **Wrongable**: May be incorrect
