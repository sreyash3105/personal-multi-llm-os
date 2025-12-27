"""
vision_confidence.py (Phase B)

Extract and assess confidence from Vision/OCR results.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


def extract_vision_ocr_confidence(vision_result: Dict[str, Any]) -> float:
    """
    Extract confidence for OCR/text extraction results.

    Heuristic based on:
    - Text length and quality
    - Presence of error indicators
    - Character diversity

    Args:
        vision_result: Vision result dict from LLaVA

    Returns:
        Confidence score between 0.0 and 1.0
    """
    response = vision_result.get("response", "").strip()
    if not response:
        return 0.0

    confidence_score = 0.5  # Base confidence

    # Factor 1: Response length
    if len(response) < 10:
        confidence_score -= 0.2  # Very short responses likely failed
    elif len(response) > 100:
        confidence_score += 0.1  # Longer responses more detailed

    # Factor 2: Check for error/placeholder text
    error_patterns = [
        r"i cannot see",
        r"unable to read",
        r"no text found",
        r"image unclear",
        r"sorry,? i",
        r"i'm sorry",
        r"i apologize",
        r"cannot determine",
    ]
    error_matches = sum(1 for pattern in error_patterns if re.search(pattern, response.lower()))
    if error_matches > 0:
        confidence_score -= 0.2 * min(error_matches, 3)

    # Factor 3: Character diversity (more unique chars = more likely real text)
    unique_chars = len(set(response))
    if unique_chars < 10:
        confidence_score -= 0.1  # Low diversity suggests gibberish

    # Factor 4: Check for JSON-like structure (good for structured responses)
    if "{" in response and "}" in response:
        confidence_score += 0.1

    # Clamp to valid range
    confidence_score = max(0.0, min(1.0, confidence_score))

    logger.debug(f"Vision OCR confidence calculated: {confidence_score:.3f} for response: '{response[:50]}...'")
    return confidence_score


def extract_vision_location_confidence(vision_result: Dict[str, Any]) -> float:
    """
    Extract confidence for UI element location results.

    Based on:
    - Presence of coordinates
    - Confidence value from model (if provided)
    - Element name clarity

    Args:
        vision_result: Screen locator result dict

    Returns:
        Confidence score between 0.0 and 1.0
    """
    confidence_score = 0.5  # Base confidence

    # Check for coordinates
    if "coordinates" in vision_result and vision_result["coordinates"]:
        confidence_score += 0.2
    else:
        return 0.0  # No coordinates = no confidence

    # Use model's confidence if available
    model_confidence = vision_result.get("confidence", 0.5)
    confidence_score = (confidence_score + model_confidence) / 2.0

    # Check element name quality
    element_name = vision_result.get("reasoning", "").lower()
    if "match" in element_name or "found" in element_name:
        confidence_score += 0.1

    # Clamp to valid range
    confidence_score = max(0.0, min(1.0, confidence_score))

    logger.debug(f"Vision location confidence calculated: {confidence_score:.3f}")
    return confidence_score


def extract_vision_analysis_confidence(vision_result: Dict[str, Any]) -> float:
    """
    Extract confidence for general vision analysis results.

    Heuristic based on:
    - Response length and coherence
    - Presence of specific details
    - Absence of generic responses

    Args:
        vision_result: General vision result dict

    Returns:
        Confidence score between 0.0 and 1.0
    """
    response = vision_result.get("response", "").strip()
    if not response:
        return 0.0

    confidence_score = 0.5  # Base confidence

    # Factor 1: Length
    if len(response) < 20:
        confidence_score -= 0.2
    elif len(response) > 200:
        confidence_score += 0.1

    # Factor 2: Check for generic responses
    generic_phrases = [
        "i see an image",
        "the image shows",
        "it appears to be",
        "i cannot tell",
        "not sure",
    ]
    generic_matches = sum(1 for phrase in generic_phrases if phrase in response.lower())
    if generic_matches > 0:
        confidence_score -= 0.1 * min(generic_matches, 2)

    # Factor 3: Specific details (numbers, technical terms)
    has_numbers = bool(re.search(r'\d', response))
    has_technical = any(term in response.lower() for term in ["button", "menu", "window", "text", "color"])

    if has_numbers or has_technical:
        confidence_score += 0.1

    # Clamp to valid range
    confidence_score = max(0.0, min(1.0, confidence_score))

    logger.debug(f"Vision analysis confidence calculated: {confidence_score:.3f}")
    return confidence_score


def validate_vision_result(vision_result: Dict[str, Any], mode: str = "auto") -> Dict[str, Any]:
    """
    Validate and enrich vision result with confidence metadata.

    Args:
        vision_result: Raw vision result dict
        mode: Vision mode ("ocr", "location", "analysis", etc.)

    Returns:
        Enriched vision result with confidence metadata
    """
    from .confidence_gates import validate_perception_result

    # Determine confidence extraction method based on mode
    if mode == "ocr":
        confidence_score = extract_vision_ocr_confidence(vision_result)
        source = "vision_ocr"
    elif mode in ["code", "debug"] and "coordinates" in vision_result:
        confidence_score = extract_vision_location_confidence(vision_result)
        source = "vision_location"
    else:
        confidence_score = extract_vision_analysis_confidence(vision_result)
        source = "vision_analysis"

    # Override confidence in result
    vision_result["confidence"] = confidence_score

    return validate_perception_result(vision_result, source)