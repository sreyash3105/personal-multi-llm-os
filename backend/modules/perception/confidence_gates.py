"""
confidence_gates.py (Phase B)

Core gating logic for perception confidence.
Determines if perception results are trustworthy enough for action.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
import logging

from backend.core.config import (
    PERCEPTION_CONFIDENCE_LOW_THRESHOLD,
    PERCEPTION_CONFIDENCE_MEDIUM_THRESHOLD,
    PERCEPTION_CONFIDENCE_HIGH_THRESHOLD,
    PERCEPTION_CONFIRM_REQUIRED,
)

logger = logging.getLogger(__name__)


class ConfidenceLevel:
    """Enumeration of confidence levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


def evaluate_confidence_level(confidence_score: float) -> str:
    """
    Evaluate numerical confidence score into categorical level.

    Args:
        confidence_score: Float between 0.0 and 1.0

    Returns:
        Confidence level string
    """
    if confidence_score < PERCEPTION_CONFIDENCE_LOW_THRESHOLD:
        return ConfidenceLevel.LOW
    elif confidence_score < PERCEPTION_CONFIDENCE_MEDIUM_THRESHOLD:
        return ConfidenceLevel.MEDIUM
    elif confidence_score < PERCEPTION_CONFIDENCE_HIGH_THRESHOLD:
        return ConfidenceLevel.HIGH
    else:
        return ConfidenceLevel.VERY_HIGH


def should_require_confirmation(confidence_level: str, operation_risk: float = 0.0) -> bool:
    """
    Determine if user confirmation is required based on confidence and risk.

    Args:
        confidence_level: Categorical confidence level
        operation_risk: Risk score from security assessment (0.0-10.0)

    Returns:
        True if confirmation required, False if can proceed
    """
    if not PERCEPTION_CONFIRM_REQUIRED:
        return False

    # Always require confirmation for low confidence
    if confidence_level == ConfidenceLevel.LOW:
        return True

    # Require confirmation for medium confidence
    if confidence_level == ConfidenceLevel.MEDIUM:
        return True

    # For high confidence, require confirmation only for high-risk operations
    if confidence_level == ConfidenceLevel.HIGH and operation_risk > 5.0:
        return True

    # Very high confidence with low risk can proceed without confirmation
    return False


def create_confidence_metadata(confidence_score: float, source: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create standardized confidence metadata for perception results.

    Args:
        confidence_score: Numerical confidence (0.0-1.0)
        source: Source type ("stt", "vision_ocr", "vision_location", "vision_analysis")
        details: Optional additional confidence details

    Returns:
        Confidence metadata dict
    """
    level = evaluate_confidence_level(confidence_score)

    metadata = {
        "confidence_score": confidence_score,
        "confidence_level": level,
        "confidence_source": source,
        "requires_confirmation": should_require_confirmation(level),
        "timestamp": __import__('time').time(),
    }

    if details:
        metadata["confidence_details"] = details

    return metadata


def validate_perception_result(result: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Validate and enrich a perception result with confidence metadata.

    Args:
        result: Raw perception result dict
        source: Perception source type

    Returns:
        Enriched result with confidence metadata
    """
    # Extract confidence score from result if present
    confidence_score = result.get("confidence", result.get("confidence_score", 0.5))

    # Ensure confidence is in valid range
    confidence_score = max(0.0, min(1.0, float(confidence_score)))

    # Create metadata
    confidence_meta = create_confidence_metadata(confidence_score, source)

    # Add to result
    result["confidence_metadata"] = confidence_meta

    # Log confidence assessment
    level = confidence_meta["confidence_level"]
    logger.info(f"Perception confidence assessed: {source}={confidence_score:.3f} ({level})")

    return result