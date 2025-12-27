"""
Read-Only PatternReport Output

AIOS Next Frontier - Pattern Aggregation Layer

Read-only report of detected misuse patterns.
Facts only - no recommendations, no warnings, no calls to action.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core.pattern_event import PatternType


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

    Keys: PatternType enum values
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
                    pattern_type.value: count  # Would need profile-specific breakdown
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
