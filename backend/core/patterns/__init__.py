"""
Pattern Aggregation Layer

AIOS Next Frontier - Consolidated Exports

Consolidates PatternEvent schema, PatternReport, and all enums.
Centralized exports for clean imports.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


# ==========================
# ENUMS
# ==========================

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


# ==========================
# DATA CLASSES
# ==========================

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


@dataclass(frozen=True)
class PatternReport:
    """
    Read-only report of pattern observations.

    Mirrors behavior without judgment.
    No recommendations.
    No calls to action.
    """

    # Report Metadata
    report_generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    """
    When this report was generated.
    ISO-8601 format.
    """

    # Summary Statistics
    total_pattern_events: int = 0
    """
    Total number of pattern events recorded.
    """

    unique_profiles: int = 0
    """
    Number of unique profiles with pattern events.
    """

    # Pattern Type Breakdown
    pattern_counts: Dict[str, int] = field(default_factory=dict)
    """
    Count of events by pattern type.

    Keys: string values
    Values: Event counts

    Example:
        {
            "REPEATED_LOW_CONFIDENCE": 15,
            "IMMEDIATE_CONFIRM_AFTER_FRICTION": 8,
            "IDENTICAL_REFUSAL_BYPASS": 3,
        }
    """

    # Severity Breakdown
    severity_counts: Dict[str, int] = field(default_factory=dict)
    """
    Count of events by severity level.

    Keys: PatternSeverity enum values
    Values: Event counts

    Example:
        {
            "LOW": 5,
            "MEDIUM": 12,
            "HIGH": 9,
        }
    """

    # Recent Patterns (last 24 hours)
    recent_patterns: List[Dict[str, Any]] = field(default_factory=list)
    """
    Pattern events from last 24 hours.

    Each item contains:
        - pattern_id
        - pattern_type
        - pattern_severity
        - timestamp
        - profile_id
        - triggering_action
        - pattern_details

    READ-ONLY.
    NO modification.
    """

    # Top Profiles by Pattern Frequency
    top_profiles: List[Dict[str, Any]] = field(default_factory=list)
    """
    Profiles with highest pattern event counts.

    Each item contains:
        - profile_id
        - total_patterns
        - pattern_breakdown

    Sorted by total_patterns DESC.
    """

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert report to dictionary.

        NO transformation.
        NO omission.
        NO judgment.
        """
        return {
            "report_generated_at": self.report_generated_at,
            "total_pattern_events": self.total_pattern_events,
            "unique_profiles": self.unique_profiles,
            "pattern_counts": self.pattern_counts,
            "severity_counts": self.severity_counts,
            "recent_patterns": self.recent_patterns,
            "top_profiles": self.top_profiles,
        }

    @staticmethod
    def generate_from_statistics(
        all_statistics: List[Dict[str, Any]],
        recent_events: List[Dict[str, Any]],
        profile_counts: Dict[str, int],
    ) -> "PatternReport":
        """
        Generate PatternReport from aggregated data.

        Parameters:
            all_statistics: Statistics by pattern type (from PatternRecord.get_statistics)
            recent_events: Events from last 24 hours
            profile_counts: Total pattern counts per profile

        Returns:
            PatternReport with all populated fields

        Constraints:
            - NO recommendations
            - NO warnings
            - NO calls to action
            - PURE aggregation of facts
        """
        total_events = sum(s["count"] for s in all_statistics)

        pattern_counts = {
            s["pattern_type"]: s["count"]
            for s in all_statistics
        }

        severity_counts = {
            "LOW": 0,
            "MEDIUM": 0,
            "HIGH": 0,
        }

        # Count severity levels from recent events
        for event in recent_events:
            sev = event.get("pattern_severity", "LOW")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Sort profiles by total pattern count
        sorted_profiles = sorted(
            profile_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        top_profiles = [
            {
                "profile_id": profile_id,
                "total_patterns": count,
                "pattern_breakdown": {
                    pattern_type.value: count
                    for pattern_type in PatternType
                },
            }
            for profile_id, count in sorted_profiles[:10]
        ]

        return PatternReport(
            total_pattern_events=total_events,
            unique_profiles=len(profile_counts),
            pattern_counts=pattern_counts,
            severity_counts=severity_counts,
            recent_patterns=recent_events,
            top_profiles=top_profiles,
        )

    def format_as_text(self) -> str:
        """
        Format report as plain text.

        NO recommendations.
        NO warnings.
        NO interpretation.

        Just facts.
        """
        lines = [
            "PATTERN OBSERVATION REPORT",
            "=" * 50,
            f"Generated: {self.report_generated_at}",
            "",
            f"Total Pattern Events: {self.total_pattern_events}",
            f"Unique Profiles: {self.unique_profiles}",
            "",
            "Pattern Type Breakdown:",
            "-" * 30,
        ]

        for pattern_type, count in sorted(
            self.pattern_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            lines.append(f"  {pattern_type}: {count}")

        lines.extend([
            "",
            "Severity Breakdown:",
            "-" * 30,
            f"  LOW: {self.severity_counts.get('LOW', 0)}",
            f"  MEDIUM: {self.severity_counts.get('MEDIUM', 0)}",
            f"  HIGH: {self.severity_counts.get('HIGH', 0)}",
            "",
            "Top Profiles by Pattern Frequency:",
            "-" * 30,
        ])

        for i, profile in enumerate(self.top_profiles[:5], 1):
            lines.append(
                f"  {i}. Profile {profile['profile_id']}: "
                f"{profile['total_patterns']} pattern events"
            )

        lines.extend([
            "",
            "Recent Patterns (Last 24 Hours):",
            "-" * 30,
        ])

        for event in self.recent_patterns[:10]:
            lines.append(
                f"  [{event['timestamp']}] {event['pattern_type']} "
                f"- Profile {event['profile_id']}"
            )

        lines.append("")
        lines.append("=" * 50)
        lines.append("END OF REPORT")
        lines.append("NOTE: This report contains observed facts only.")
        lines.append("No recommendations are provided.")
        lines.append("No action is required or suggested.")

        return "\n".join(lines)


# ==========================
# PUBLIC API
# ==========================

__all__ = [
    # Enums
    "PatternType",
    "PatternSeverity",
    # Dataclasses
    "PatternEvent",
    "PatternReport",
]
