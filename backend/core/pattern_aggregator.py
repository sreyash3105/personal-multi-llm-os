"""
PatternAggregator Interface

AIOS Next Frontier - Pattern Aggregation Layer

Interface for detecting and recording misuse patterns.
Read-only observation - no enforcement, no adaptation.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from backend.core.pattern_event import PatternEvent, PatternType, PatternSeverity


class PatternAggregator(ABC):
    """
    Interface for pattern aggregation.

    Responsibilities:
    - Detect patterns from system events
    - Record patterns persistently
    - Provide read-only pattern reports
    - NEVER adapt system behavior

    Responsibilities EXPLICITLY FORBIDDEN:
    - Block actions based on patterns
    - Slow actions based on patterns
    - Adapt thresholds
    - Escalate severity
    - Introduce new friction
    - Change behavior based on patterns
    """

    @abstractmethod
    def record_pattern(
        self,
        pattern_type: PatternType,
        severity: PatternSeverity,
        profile_id: str,
        session_id: Optional[str],
        triggering_action: str,
        pattern_details: Dict,
        related_failure_id: Optional[str] = None,
        related_action_id: Optional[str] = None,
    ) -> PatternEvent:
        """
        Record a single pattern event.

        Parameters:
            pattern_type: Type of pattern detected
            severity: Severity of this pattern instance
            profile_id: User profile involved
            session_id: Session context (optional)
            triggering_action: What action triggered pattern detection
            pattern_details: Specific data about pattern
            related_failure_id: Reference to FailureEvent if applicable
            related_action_id: Reference to action if applicable

        Returns:
            Created PatternEvent

        Constraints:
            - NO behavior modification
            - NO threshold adaptation
            - NO user notification
            - PURE recording
        """
        pass

    @abstractmethod
    def get_patterns_by_profile(
        self,
        profile_id: str,
        pattern_type: Optional[PatternType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[PatternEvent]:
        """
        Query patterns for a specific profile.

        Parameters:
            profile_id: User profile to query
            pattern_type: Filter by pattern type (optional)
            start_time: Start of time range (optional)
            end_time: End of time range (optional)
            limit: Maximum number of results

        Returns:
            List of PatternEvent matching query

        Constraints:
            - READ-ONLY
            - NO behavior modification
        """
        pass

    @abstractmethod
    def get_pattern_frequency(
        self,
        pattern_type: PatternType,
        profile_id: Optional[str] = None,
        time_window: Optional[timedelta] = None,
    ) -> int:
        """
        Get count of pattern occurrences.

        Parameters:
            pattern_type: Type of pattern to count
            profile_id: Filter by profile (optional, None = all profiles)
            time_window: Time window for count (optional, None = all time)

        Returns:
            Count of pattern occurrences

        Constraints:
            - READ-ONLY
            - NO behavior modification
        """
        pass

    @abstractmethod
    def get_last_occurrence(
        self,
        pattern_type: PatternType,
        profile_id: Optional[str] = None,
    ) -> Optional[PatternEvent]:
        """
        Get most recent occurrence of a pattern.

        Parameters:
            pattern_type: Type of pattern to query
            profile_id: Filter by profile (optional, None = all profiles)

        Returns:
            Most recent PatternEvent, or None if not found

        Constraints:
            - READ-ONLY
            - NO behavior modification
        """
        pass


class PatternDetector(ABC):
    """
    Interface for pattern detection logic.

    Responsibilities:
    - Detect patterns from system state
    - Create PatternEvents when patterns found
    - NO adaptation of detection logic
    - NO threshold tuning
    """

    @abstractmethod
    def detect_low_confidence_persistence(
        self,
        profile_id: str,
        session_id: Optional[str],
        current_confidence: float,
        confidence_threshold: float,
        recent_attempts: int,
        time_window: timedelta,
    ) -> Optional[PatternEvent]:
        """
        Detect repeated low-confidence action attempts.

        Returns PatternEvent if pattern detected, None otherwise.
        """
        pass

    @abstractmethod
    def detect_immediate_confirm_after_friction(
        self,
        profile_id: str,
        session_id: Optional[str],
        friction_duration_seconds: int,
        confirmation_time_seconds: float,
        action_id: str,
    ) -> Optional[PatternEvent]:
        """
        Detect immediate confirmation after friction countdown.

        Returns PatternEvent if pattern detected, None otherwise.
        """
        pass

    @abstractmethod
    def detect_identical_refusal_bypass(
        self,
        profile_id: str,
        session_id: Optional[str],
        current_request: str,
        last_refusal_request: str,
        last_refusal_time: datetime,
        time_window: timedelta,
    ) -> Optional[PatternEvent]:
        """
        Detect retry of identical request after refusal.

        Returns PatternEvent if pattern detected, None otherwise.
        """
        pass

    @abstractmethod
    def detect_warning_dismissal_without_read(
        self,
        profile_id: str,
        session_id: Optional[str],
        warning_text_length: int,
        dismiss_time_seconds: float,
        human_read_speed_chars_per_second: float = 200.0,
    ) -> Optional[PatternEvent]:
        """
        Detect warning dismissal faster than human reading speed.

        Returns PatternEvent if pattern detected, None otherwise.
        """
        pass

    @abstractmethod
    def detect_repeated_friction_cancel(
        self,
        profile_id: str,
        session_id: Optional[str],
        cancel_count_in_window: int,
        time_window: timedelta,
    ) -> Optional[PatternEvent]:
        """
        Detect repeated initiation then cancellation during friction.

        Returns PatternEvent if pattern detected, None otherwise.
        """
        pass

    @abstractmethod
    def detect_simplified_request_for_higher_confidence(
        self,
        profile_id: str,
        session_id: Optional[str],
        original_request: str,
        simplified_request: str,
        original_confidence: float,
        simplified_confidence: float,
        request_similarity_threshold: float = 0.7,
    ) -> Optional[PatternEvent]:
        """
        Detect request simplification to avoid low-confidence classification.

        Returns PatternEvent if pattern detected, None otherwise.
        """
        pass
