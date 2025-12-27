"""
stt_confidence.py (Phase B)

Extract and assess confidence from STT (Speech-to-Text) results.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def extract_stt_confidence(stt_result: Dict[str, Any]) -> float:
    """
    Extract confidence score from STT result.

    For faster-whisper, confidence is typically not directly available.
    This provides a heuristic confidence based on:
    - Audio length vs text length ratio
    - Presence of repeated words (indicating uncertainty)
    - Language detection confidence (if available)

    Args:
        stt_result: STT result dict from faster-whisper

    Returns:
        Confidence score between 0.0 and 1.0
    """
    text = stt_result.get("text", "").strip()
    if not text:
        return 0.0

    confidence_score = 0.5  # Base confidence

    # Factor 1: Text length relative to expected (rough heuristic)
    word_count = len(text.split())
    if word_count < 2:
        confidence_score -= 0.2  # Very short responses likely errors
    elif word_count > 50:
        confidence_score += 0.1  # Longer responses more likely correct

    # Factor 2: Language detection (if available)
    language = stt_result.get("language")
    language_probability = stt_result.get("language_probability")
    if language_probability is not None:
        # Normalize to 0-1 scale if needed
        if language_probability > 1.0:
            language_probability /= 100.0  # Assume percentage
        confidence_score = (confidence_score + language_probability) / 2.0

    # Factor 3: Check for repeated words (uncertainty indicator)
    words = text.lower().split()
    if len(words) > 1:
        repeated_words = sum(1 for i in range(len(words)-1) if words[i] == words[i+1])
        if repeated_words > 0:
            confidence_score -= 0.1 * min(repeated_words, 3)

    # Factor 4: Check for placeholder/error text
    error_indicators = ["[silence]", "[inaudible]", "error", "unknown"]
    if any(indicator in text.lower() for indicator in error_indicators):
        confidence_score -= 0.3

    # Clamp to valid range
    confidence_score = max(0.0, min(1.0, confidence_score))

    logger.debug(f"STT confidence calculated: {confidence_score:.3f} for text: '{text[:50]}...'")
    return confidence_score


def validate_stt_result(stt_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and enrich STT result with confidence metadata.

    Args:
        stt_result: Raw STT result dict

    Returns:
        Enriched STT result with confidence metadata
    """
    from .confidence_gates import validate_perception_result

    return validate_perception_result(stt_result, "stt")