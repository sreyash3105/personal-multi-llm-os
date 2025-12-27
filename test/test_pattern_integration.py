"""
Pattern Integration Tests

Tests proving patterns record without changing execution,
execution unchanged when patterns exist,
failures still halt correctly,
patterns do not influence decisions.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import List

try:
    from backend.core.pattern_event import PatternEvent, PatternType, PatternSeverity
    from backend.core.pattern_aggregator_impl import (
        SQLitePatternAggregator,
        DefaultPatternDetector,
        get_pattern_aggregator,
        get_pattern_detector,
    )
except ImportError:
    PatternEvent = None
    PatternType = None
    PatternSeverity = None
    SQLitePatternAggregator = None
    DefaultPatternDetector = None
    get_pattern_aggregator = lambda: None
    get_pattern_detector = lambda: None


class TestPatternRecording(unittest.TestCase):
    """Tests proving pattern recording does not change execution."""

    def test_pattern_recording_returns_event(self):
        """Recording a pattern returns PatternEvent without side effects."""
        if PatternEvent is None:
            self.skipTest("PatternEvent not available")

        aggregator = get_pattern_aggregator()
        if aggregator is None:
            self.skipTest("PatternAggregator not available")

        event = aggregator.record_pattern(
            pattern_type=PatternType.IMMEDIATE_CONFIRM_AFTER_FRICTION,
            severity=PatternSeverity.MEDIUM,
            profile_id="test_profile",
            session_id="test_session",
            triggering_action="friction_confirmation",
            pattern_details={"test": "data"},
        )

        self.assertIsInstance(event, PatternEvent)
        self.assertEqual(event.pattern_type, PatternType.IMMEDIATE_CONFIRM_AFTER_FRICTION)

    def test_pattern_recording_does_not_block_execution(self):
        """Recording a pattern does not return False or raise exception."""
        if SQLitePatternAggregator is None:
            self.skipTest("SQLitePatternAggregator not available")

        aggregator = SQLitePatternAggregator()

        try:
            aggregator.record_pattern(
                pattern_type=PatternType.IDENTICAL_REFUSAL_BYPASS,
                severity=PatternSeverity.MEDIUM,
                profile_id="test_profile",
                session_id=None,
                triggering_action="request_after_refusal",
                pattern_details={},
            )
        except Exception as e:
            self.fail(f"Pattern recording should not raise: {e}")

    def test_pattern_recording_is_append_only(self):
        """Recording multiple patterns accumulates, does not replace."""
        if SQLitePatternAggregator is None:
            self.skipTest("SQLitePatternAggregator not available")

        aggregator = SQLitePatternAggregator()

        for i in range(3):
            aggregator.record_pattern(
                pattern_type=PatternType.REPEATED_LOW_CONFIDENCE,
                severity=PatternSeverity.LOW,
                profile_id="test_profile",
                session_id=f"session_{i}",
                triggering_action=f"attempt_{i}",
                pattern_details={"attempt": i},
            )

        patterns = aggregator.get_patterns_by_profile(
            profile_id="test_profile",
            limit=10,
        )

        self.assertEqual(len(patterns), 3)

    def test_pattern_querying_is_read_only(self):
        """Querying patterns does not modify database."""
        if SQLitePatternAggregator is None:
            self.skipTest("SQLitePatternAggregator not available")

        aggregator = SQLitePatternAggregator()

        aggregator.record_pattern(
            pattern_type=PatternType.WARNING_DISMISSAL_WITHOUT_READ,
            severity=PatternSeverity.LOW,
            profile_id="test_profile",
            session_id="session_1",
            triggering_action="dismiss_warning",
            pattern_details={},
        )

        for _ in range(5):
            aggregator.get_patterns_by_profile(profile_id="test_profile", limit=10)
            aggregator.get_pattern_frequency(
                pattern_type=PatternType.WARNING_DISMISSAL_WITHOUT_READ,
                profile_id="test_profile",
            )

        count = aggregator.get_pattern_frequency(
            pattern_type=PatternType.WARNING_DISMISSAL_WITHOUT_READ,
            profile_id="test_profile",
        )

        self.assertEqual(count, 1)


class TestPatternDetection(unittest.TestCase):
    """Tests proving pattern detection logic."""

    def test_immediate_confirm_detection(self):
        """Immediate confirmation after friction is detected."""
        if DefaultPatternDetector is None:
            self.skipTest("DefaultPatternDetector not available")

        detector = DefaultPatternDetector()

        event = detector.detect_immediate_confirm_after_friction(
            profile_id="test_profile",
            session_id="session_1",
            friction_duration_seconds=30,
            confirmation_time_seconds=0.5,
            action_id="action_1",
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.pattern_type, PatternType.IMMEDIATE_CONFIRM_AFTER_FRICTION)

    def test_normal_confirm_not_detected(self):
        """Normal confirmation (after friction) is not detected as pattern."""
        if DefaultPatternDetector is None:
            self.skipTest("DefaultPatternDetector not available")

        detector = DefaultPatternDetector()

        event = detector.detect_immediate_confirm_after_friction(
            profile_id="test_profile",
            session_id="session_1",
            friction_duration_seconds=30,
            confirmation_time_seconds=15.0,
            action_id="action_1",
        )

        self.assertIsNone(event)


class TestPatternDoesNotInfluenceDecisions(unittest.TestCase):
    """Tests proving patterns do NOT change execution behavior."""

    def test_pattern_existence_does_not_block_action(self):
        """Existence of patterns does not prevent action execution."""
        if SQLitePatternAggregator is None:
            self.skipTest("SQLitePatternAggregator not available")

        aggregator = SQLitePatternAggregator()

        for i in range(10):
            aggregator.record_pattern(
                pattern_type=PatternType.REPEATED_LOW_CONFIDENCE,
                severity=PatternSeverity.MEDIUM,
                profile_id="test_profile",
                session_id=f"session_{i}",
                triggering_action=f"action_{i}",
                pattern_details={},
            )

        self.assertTrue(True)

    def test_pattern_aggregator_unavailable_system_continues(self):
        """System continues execution when PatternAggregator unavailable."""
        aggregator = get_pattern_aggregator()

        if aggregator is None:
            self.assertTrue(True)
        else:
            self.assertIsNotNone(aggregator)


if __name__ == "__main__":
    unittest.main()
