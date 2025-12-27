"""
Concrete PatternAggregator Implementation

AIOS Next Frontier - Pattern Aggregation Layer

Implements PatternAggregator interface using PatternRecord persistence.
Append-only recording - no enforcement, no adaptation.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from difflib import SequenceMatcher

try:
    from backend.core.pattern_aggregator import PatternAggregator, PatternDetector
    from backend.core.pattern_event import PatternEvent, PatternType, PatternSeverity
    from backend.core.pattern_record import PatternRecord
except ImportError:
    PatternAggregator = None
    PatternDetector = None
    PatternEvent = None
    PatternType = None
    PatternSeverity = None
    PatternRecord = None


class SQLitePatternAggregator(PatternAggregator):
    """
    Concrete implementation using SQLite persistence.

    Recording only - no behavior modification.
    """

    def record_pattern(
        self,
        pattern_type: PatternType,
        severity: PatternSeverity,
        profile_id: str,
        session_id: Optional[str],
        triggering_action: str,
        pattern_details: dict,
        related_failure_id: Optional[str] = None,
        related_action_id: Optional[str] = None,
    ) -> PatternEvent:
        """
        Record pattern event to persistent storage.

        PURE recording - no side effects on execution.
        """
        event = PatternEvent(
            pattern_type=pattern_type,
            pattern_severity=severity,
            context_snapshot={
                "profile_id": profile_id,
                "session_id": session_id,
                "triggering_action": triggering_action,
                "pattern_details": pattern_details,
            },
            related_failure_id=related_failure_id,
            related_action_id=related_action_id,
        )

        PatternRecord.insert(event)
        return event

    def get_patterns_by_profile(
        self,
        profile_id: str,
        pattern_type: Optional[PatternType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[PatternEvent]:
        """
        Query patterns by profile.

        READ-ONLY - no behavior modification.
        """
        raw_records = PatternRecord.query_by_profile(
            profile_id=profile_id,
            pattern_type=pattern_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

        return [PatternEvent.from_dict(r) for r in raw_records]

    def get_pattern_frequency(
        self,
        pattern_type: PatternType,
        profile_id: Optional[str] = None,
        time_window: Optional[timedelta] = None,
    ) -> int:
        """
        Count pattern occurrences.

        READ-ONLY - no behavior modification.
        """
        return PatternRecord.count_by_type(
            pattern_type=pattern_type,
            profile_id=profile_id,
            time_window=time_window,
        )

    def get_last_occurrence(
        self,
        pattern_type: PatternType,
        profile_id: Optional[str] = None,
    ) -> Optional[PatternEvent]:
        """
        Get most recent pattern occurrence.

        READ-ONLY - no behavior modification.
        """
        raw_record = PatternRecord.get_last_occurrence(
            pattern_type=pattern_type,
            profile_id=profile_id,
        )

        if raw_record is None:
            return None

        return PatternEvent.from_dict(raw_record)


class DefaultPatternDetector(PatternDetector):
    """
    Concrete implementation of pattern detection logic.

    Detection only - no adaptation of thresholds.
    """

    LOW_CONFIDENCE_THRESHOLD = 0.6
    LOW_CONFIDENCE_WINDOW = timedelta(minutes=5)
    LOW_CONFIDENCE_COUNT_THRESHOLD = 3

    IMMEDIATE_CONFIRM_THRESHOLD_SECONDS = 1.0

    IDENTICAL_REQUEST_WINDOW = timedelta(minutes=2)
    REQUEST_SIMILARITY_THRESHOLD = 0.9

    WARNING_DISMISSAL_THRESHOLD_MULTIPLIER = 0.1  # 10% of reading time

    FRICTION_CANCEL_WINDOW = timedelta(minutes=10)
    FRICTION_CANCEL_COUNT = 3

    REQUEST_SIMILARITY_THRESHOLD_HIGH_CONFIDENCE = 0.7

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

        Returns pattern if recent_attempts >= threshold within time_window.
        """
        if current_confidence >= confidence_threshold:
            return None

        if recent_attempts < self.LOW_CONFIDENCE_COUNT_THRESHOLD:
            return None

        return None  # Would return PatternEvent if aggregating history

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

        Returns pattern if confirmation_time < IMMEDIATE_CONFIRM_THRESHOLD_SECONDS.
        """
        if confirmation_time_seconds >= self.IMMEDIATE_CONFIRM_THRESHOLD_SECONDS:
            return None

        return PatternEvent(
            pattern_type=PatternType.IMMEDIATE_CONFIRM_AFTER_FRICTION,
            pattern_severity=PatternSeverity.MEDIUM,
            context_snapshot={
                "profile_id": profile_id,
                "session_id": session_id,
                "triggering_action": f"friction_confirmation:{action_id}",
                "pattern_details": {
                    "friction_duration_seconds": friction_duration_seconds,
                    "confirmation_time_seconds": confirmation_time_seconds,
                    "immediate_threshold_seconds": self.IMMEDIATE_CONFIRM_THRESHOLD_SECONDS,
                },
            },
            related_action_id=action_id,
        )

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

        Returns pattern if:
        1. Within time window
        2. Requests are identical (similarity >= threshold)
        """
        time_since_refusal = datetime.utcnow() - last_refusal_time
        if time_since_refusal > time_window:
            return None

        similarity = SequenceMatcher(None, current_request, last_refusal_request).ratio()
        if similarity < self.REQUEST_SIMILARITY_THRESHOLD:
            return None

        return PatternEvent(
            pattern_type=PatternType.IDENTICAL_REFUSAL_BYPASS,
            pattern_severity=PatternSeverity.MEDIUM,
            context_snapshot={
                "profile_id": profile_id,
                "session_id": session_id,
                "triggering_action": "request_after_refusal",
                "pattern_details": {
                    "request_similarity": similarity,
                    "similarity_threshold": self.REQUEST_SIMILARITY_THRESHOLD,
                    "time_since_refusal_seconds": time_since_refusal.total_seconds(),
                },
            },
        )

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

        Returns pattern if dismiss_time < 10% of expected read time.
        """
        expected_read_time = warning_text_length / human_read_speed_chars_per_second
        min_acceptable_time = expected_read_time * self.WARNING_DISMISSAL_THRESHOLD_MULTIPLIER

        if dismiss_time_seconds >= min_acceptable_time:
            return None

        return PatternEvent(
            pattern_type=PatternType.WARNING_DISMISSAL_WITHOUT_READ,
            pattern_severity=PatternSeverity.LOW,
            context_snapshot={
                "profile_id": profile_id,
                "session_id": session_id,
                "triggering_action": "warning_dismissal",
                "pattern_details": {
                    "warning_text_length": warning_text_length,
                    "expected_read_time_seconds": expected_read_time,
                    "dismiss_time_seconds": dismiss_time_seconds,
                    "min_acceptable_time_seconds": min_acceptable_time,
                },
            },
        )

    def detect_repeated_friction_cancel(
        self,
        profile_id: str,
        session_id: Optional[str],
        cancel_count_in_window: int,
        time_window: timedelta,
    ) -> Optional[PatternEvent]:
        """
        Detect repeated initiation then cancellation during friction.

        Returns pattern if cancel_count >= threshold within time_window.
        """
        if cancel_count_in_window < self.FRICTION_CANCEL_COUNT:
            return None

        return PatternEvent(
            pattern_type=PatternType.REPEATED_FRICTION_CANCEL,
            pattern_severity=PatternSeverity.MEDIUM,
            context_snapshot={
                "profile_id": profile_id,
                "session_id": session_id,
                "triggering_action": "friction_cancel",
                "pattern_details": {
                    "cancel_count_in_window": cancel_count_in_window,
                    "time_window_seconds": time_window.total_seconds(),
                    "cancel_threshold": self.FRICTION_CANCEL_COUNT,
                },
            },
        )

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

        Returns pattern if:
        1. Simplified confidence > original confidence
        2. Requests are similar enough (likely same intent)
        """
        if simplified_confidence <= original_confidence:
            return None

        similarity = SequenceMatcher(None, original_request, simplified_request).ratio()
        if similarity < request_similarity_threshold:
            return None

        return PatternEvent(
            pattern_type=PatternType.SIMPLIFIED_REQUEST_FOR_HIGHER_CONFIDENCE,
            pattern_severity=PatternSeverity.MEDIUM,
            context_snapshot={
                "profile_id": profile_id,
                "session_id": session_id,
                "triggering_action": "request_simplification",
                "pattern_details": {
                    "original_confidence": original_confidence,
                    "simplified_confidence": simplified_confidence,
                    "request_similarity": similarity,
                    "similarity_threshold": request_similarity_threshold,
                },
            },
        )


# Global shared instance for integration
_pattern_aggregator: Optional[SQLitePatternAggregator] = None
_pattern_detector: Optional[DefaultPatternDetector] = None


def get_pattern_aggregator() -> Optional[SQLitePatternAggregator]:
    """
    Get shared PatternAggregator instance.

    Returns None if not available or fails to initialize.
    System must continue if unavailable.
    """
    global _pattern_aggregator

    if _pattern_aggregator is None:
        try:
            _pattern_aggregator = SQLitePatternAggregator()
        except Exception:
            _pattern_aggregator = None

    return _pattern_aggregator


def get_pattern_detector() -> Optional[DefaultPatternDetector]:
    """
    Get shared PatternDetector instance.

    Returns None if not available.
    """
    global _pattern_detector

    if _pattern_detector is None:
        try:
            _pattern_detector = DefaultPatternDetector()
        except Exception:
            _pattern_detector = None

    return _pattern_detector
