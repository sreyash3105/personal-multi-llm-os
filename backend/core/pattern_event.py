"""
PatternEvent Schema

AIOS Next Frontier - Pattern Aggregation Layer

Defines schema for pattern events representing misuse indicators.
Patterns are mirrors only - no behavior modification, no enforcement.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class PatternType(Enum):
    """
    Enumeration of detectable misuse patterns.

    Patterns are indicators of performative transparency:
    behaviors where truth is presented but ignored.
    """

    # Low Confidence Persistence
    REPEATED_LOW_CONFIDENCE = "REPEATED_LOW_CONFIDENCE"
    """
    User repeatedly initiates actions below confidence threshold.
    Indicates: User ignores uncertainty and proceeds anyway.
    """

    # Immediate Confirmation Pattern
    IMMEDIATE_CONFIRM_AFTER_FRICTION = "IMMEDIATE_CONFIRM_AFTER_FRICTION"
    """
    User confirms high-consequence action at minimum allowable time
    (e.g., within 1 second of 30-second countdown).
    Indicates: User waited out friction mechanically, not deliberatively.
    """

    # Rubber-Stamp Pattern
    IDENTICAL_REFUSAL_BYPASS = "IDENTICAL_REFUSAL_BYPASS"
    """
    User retries identical request after Non-Action Report without modification.
    Indicates: User ignoring refusal reasons.
    """

    # Warning Ignore Pattern
    WARNING_DISMISSAL_WITHOUT_READ = "WARNING_DISMISSAL_WITHOUT_READ"
    """
    User dismisses uncertainty warning faster than human reading speed
    (e.g., < 2 seconds for multi-line warning).
    Indicates: User clicking through without comprehension.
    """

    # Pattern of Friction Minimization
    REPEATED_FRICTION_CANCEL = "REPEATED_FRICTION_CANCEL"
    """
    User repeatedly initiates high-consequence actions then cancels
    during friction period.
    Indicates: User testing friction boundary or treating friction as formality.
    """

    # Pattern of Confidence Escalation
    SIMPLIFIED_REQUEST_FOR_HIGHER_CONFIDENCE = "SIMPLIFIED_REQUEST_FOR_HIGHER_CONFIDENCE"
    """
    User systematically simplifies requests to avoid low-confidence classification.
    Example: "Delete file" → "Do thing I said"
    Indicates: User gaming confidence system without addressing underlying uncertainty.
    """


class PatternSeverity(Enum):
    """
    Severity levels for patterns.

    These are NOT execution impact.
    These indicate frequency or intensity of pattern.
    """

    LOW = "LOW"
    """
    Pattern observed once or twice.
    May be coincidence.
    """

    MEDIUM = "MEDIUM"
    """
    Pattern observed repeatedly within short timeframe.
    Indicates consistent behavior.
    """

    HIGH = "HIGH"
    """
    Pattern observed frequently or consistently over time.
    Indicates systemic behavior.
    """


@dataclass(frozen=True)
class PatternEvent:
    """
    A single detection of a misuse pattern.

    This is a FACT, not a judgment.
    It records what happened, not why or what to do.
    """

    # Required fields (no defaults)
    pattern_type: PatternType
    """
    Type of pattern detected.
    """

    pattern_severity: PatternSeverity
    """
    Severity of this pattern instance.
    """

    context_snapshot: Dict[str, Any]
    """
    Full context at time of pattern detection.

    REQUIRED FIELDS:
        - profile_id: User profile involved
        - session_id: Session context
        - triggering_action: What action triggered pattern detection
        - pattern_details: Specific data about pattern (e.g., confirmation_time, confidence_value)

    OPTIONAL FIELDS (appended if available):
        - related_failure_id: If pattern relates to specific FailureEvent
        - previous_occurrence_count: How many times this pattern seen before
        - time_since_last_occurrence: Time delta from last pattern of same type
    """

    # Optional fields with defaults
    pattern_id: str = field(default_factory=lambda: str(uuid4()))
    """
    Unique identifier for this pattern event.
    """

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    """
    When this pattern was detected.
    ISO-8601 format.
    """

    related_failure_id: Optional[str] = None
    """
    If this pattern was triggered by a specific FailureEvent,
    reference that FailureEvent here.
    """

    related_action_id: Optional[str] = None
    """
    If this pattern was triggered by a specific action execution,
    reference that action ID here.
    """

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for storage and reporting.

        NO transformation.
        NO omission.
        NO modification.
        """
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "pattern_severity": self.pattern_severity.value,
            "timestamp": self.timestamp,
            "context_snapshot": self.context_snapshot,
            "related_failure_id": self.related_failure_id,
            "related_action_id": self.related_action_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatternEvent":
        """
        Reconstruct PatternEvent from dictionary.

        NO inference.
        NO default substitution for required fields.
        """
        required_fields = ["pattern_type", "pattern_severity", "context_snapshot"]

        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        return cls(
            pattern_id=data.get("pattern_id", str(uuid4())),
            pattern_type=PatternType[data["pattern_type"]],
            pattern_severity=PatternSeverity[data["pattern_severity"]],
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            context_snapshot=data["context_snapshot"],
            related_failure_id=data.get("related_failure_id"),
            related_action_id=data.get("related_action_id"),
        )

    def __post_init__(self):
        """
        Validate that pattern event is properly formed.
        """
        # Validate context_snapshot has required fields
        required_context = ["profile_id", "triggering_action", "pattern_details"]

        missing_context = [f for f in required_context if f not in self.context_snapshot]
        if missing_context:
            raise ValueError(
                f"context_snapshot missing required fields: {missing_context}"
            )
