"""
MEK-X: SANDBOXED INTELLIGENCE ZONE

Zero Authority. Total Containment. Maximum Power.

MEK-X may think.
MEK-X may suggest.
MEK-X may simulate.
MEK-X may be wrong.

MEK-X may never act.

Build Prompt: MEK-X — SANDBOXED INTELLIGENCE ZONE
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid
import time


class ConfidenceRange(Enum):
    """Confidence range for proposals."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass(frozen=True)
class Proposal:
    """
    MEK-X output: Proposal only.

    A Proposal is DATA ONLY.
    It does NOT grant authority.
    It does NOT trigger execution.
    It may be ignored without consequence.
    It may be wrong.
    """

    proposal_id: str
    text: str
    assumptions: List[str] = field(default_factory=list)
    confidence_range: ConfidenceRange = ConfidenceRange.MEDIUM
    known_unknowns: List[str] = field(default_factory=list)
    requested_actions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "text": self.text,
            "assumptions": self.assumptions,
            "confidence_range": self.confidence_range.value,
            "known_unknowns": self.known_unknowns,
            "requested_actions": self.requested_actions,
            "created_at": self.created_at,
        }


def create_proposal(
    text: str,
    assumptions: Optional[List[str]] = None,
    confidence_range: ConfidenceRange = ConfidenceRange.MEDIUM,
    known_unknowns: Optional[List[str]] = None,
    requested_actions: Optional[List[Dict[str, Any]]] = None,
) -> Proposal:
    """
    Create a proposal.

    This is the ONLY allowed output from MEK-X.
    """
    return Proposal(
        proposal_id=str(uuid.uuid4()),
        text=text,
        assumptions=assumptions or [],
        confidence_range=confidence_range,
        known_unknowns=known_unknowns or [],
        requested_actions=requested_actions or [],
    )
