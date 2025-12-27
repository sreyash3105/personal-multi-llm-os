"""
FAILURE TAXONOMY

AIOS Failure Articulation Layer - Artifact 1

This taxonomy enumerates all failure categories relevant to AIOS.
Each failure type has a name, description, and classification.

NO MITIGATION LOGIC ALLOWED.
NO AUTO-RESOLUTION ALLOWED.
"""

from enum import Enum
from typing import List


class FailureType(Enum):
    """
    Enumeration of all failure types in AIOS.

    Each type represents a distinct category of failure that can occur
    in the system. Failures are NOT ordered by severity; that is handled
    by separate severity classification.
    """

    # Authority and Governance Failures
    AUTHORITY_LEAKAGE = (
        "Authority granted at one scope/level is used at another scope/level "
        "without explicit re-authorization"
    )

    AUTHORITY_CONCENTRATION = (
        "Decision power consolidates in unintended components, "
        "creating de facto authorities that violate stated principles"
    )

    AUTHORITY_AMBIGUITY = (
        "It is unclear which component holds authority for a decision, "
        "leading to either deadlock or implicit authority assumption"
    )

    HIDDEN_GOVERNANCE = (
        "Decisions appear algorithmic but are actually policy-driven "
        "through implicit or invisible mechanisms"
    )

    # Temporal Failures
    TEMPORAL_DRIFT = (
        "Permissions, approvals, or authority persist beyond the mental "
        "context that produced them"
    )

    TEMPORAL_MISALIGNMENT = (
        "Concurrency causes approvals to apply to actions that no longer "
        "match the original intent"
    )

    TEMPORAL_STALENESS = (
        "Decisions execute under authority that was valid at grant time "
        "but no longer matches current intent"
    )

    # Boundary and Abstraction Failures
    BOUNDARY_VIOLATION = (
        "A component exceeds its stated responsibility or interacts with "
        "components it should not"
    )

    ABSTRACTION_WRONG = (
        "A chosen abstraction does not accurately model the reality it "
        "claims to represent"
    )

    BOUNDARY_LEAK = (
        "Internal implementation details expose through declared interfaces, "
        "creating hidden dependencies"
    )

    SCALAR_COLLAPSE = (
        "Multi-dimensional concerns (risk, impact, authority) collapse "
        "into single numeric values, losing information"
    )

    # Human and Cognitive Failures
    HUMAN_FATIGUE = (
        "Repeated human approvals become reflexive rather than considered, "
        "eroding safety without explicit rule violation"
    )

    HUMAN_RUBBER_STAMP = (
        "Precedent overrides scrutiny; humans approve based on pattern "
        "rather than case-specific evaluation"
    )

    EPISTEMIC_OVERCONFIDENCE = (
        "Humans infer completeness or causality from partial logs or data, "
        "creating false confidence"
    )

    COGNITIVE_FRAMING = (
        "System presentation (ordering, highlighting, grouping) influences "
        "human decisions without explicit acknowledgment"
    )

    HUMAN_BOTTLENECK = (
        "Human-in-the-loop becomes the limiting factor at scale, causing "
        "delays or degraded oversight"
    )

    # Observability and Truth Failures
    FALSE_CAUSALITY = (
        "Event logs imply causal relationships that do not exist, or fail "
        "to indicate uncertainty"
    )

    NARRATIVE_FRAGILITY = (
        "Event streams tell plausible but false stories when events are "
        "missing, reordered, or incomplete"
    )

    INVISIBLE_FAILURE = (
        "System fails to execute intent but presents output as success, "
        "masking the failure"
    )

    OBSERVABILITY_GAP = (
        "Critical behaviors occur without logging, making them impossible "
        "to explain after the fact"
    )

    # Ambiguity and Intent Failures
    INTENT_AMBIGUITY = (
        "System cannot determine user intent and falls through without "
        "explicit acknowledgment of ambiguity"
    )

    FALLTHROUGH_FAILURE = (
        "Ambiguity or error is masked as graceful degradation, causing "
        "silent dysfunction"
    )

    INTENT_EXHAUSTION = (
        "Repeated failure to execute intent leads to user frustration and "
        "trust decay without explicit detection"
    )

    # Meta-Governance Failures
    META_AUTHORITY = (
        "A layer that validates change itself becomes the final authority, "
        "concentrating power rather than distributing it"
    )

    GOVERNANCE_DRIFT = (
        "System behavior shifts through accumulated exceptions, temporary "
        "bypasses, or uncoordinated changes"
    )

    POLICY_CEREMONIALITY = (
        "Constitutional or governance rules exist but are bypassed in "
        "practice, becoming ceremonial rather than binding"
    )

    # Scaling and Complexity Failures
    SCALING_OVERFLOW = (
        "System design works under ideal conditions but fails under "
        "real-world load, concurrency, or time pressure"
    )

    COMPLEXITY_EXPLOSION = (
        "Number of exceptions, special cases, or state combinations grows "
        "beyond human comprehension"
    )

    FRAGMENTATION = (
        "System behavior becomes inconsistent across contexts, profiles, "
        "or sessions due to accumulated local logic"
    )

    # Safety and Risk Failures
    OVER_SAFETY_AVERSION = (
        "Excessive blocking trains users to bypass system, creating shadow "
        "workflows and actual unsafety"
    )

    FAIL_OPEN_PRESSURE = (
        "Urgency, deadlines, or incident pressure cause fail-safe mechanisms "
        "to be disabled or bypassed"
    )

    RISK_TUNING_SENSITIVITY = (
        "Small changes to risk thresholds produce large authority shifts, "
        "making governance fragile"
    )

    # Structural and Architectural Failures
    ABOUNDED_EXECUTION = (
        "Claims of bounded execution do not actually limit impact or scope "
        "of influence"
    )

    IMPACT_VS_COUNT_ERROR = (
        "System bounds by count of operations but not impact, treating "
        "one high-impact action equal to many low-impact actions"
    )

    REALITY_MISMATCH = (
        "System abstractions force all activity into formal structures "
        "(cycles, events, sessions) that do not match actual behavior"
    )

    @classmethod
    def all_types(cls) -> List["FailureType"]:
        """Return all failure types for reference."""
        return list(cls)

    @classmethod
    def description(cls, failure_type: "FailureType") -> str:
        """Get description for a failure type."""
        return failure_type.value

    @classmethod
    def by_category(cls) -> dict:
        """
        Group failure types by category for reference.

        Returns dict mapping category names to lists of FailureType enums.
        """
        categories = {
            "AUTHORITY_AND_GOVERNANCE": [
                cls.AUTHORITY_LEAKAGE,
                cls.AUTHORITY_CONCENTRATION,
                cls.AUTHORITY_AMBIGUITY,
                cls.HIDDEN_GOVERNANCE,
            ],
            "TEMPORAL": [
                cls.TEMPORAL_DRIFT,
                cls.TEMPORAL_MISALIGNMENT,
                cls.TEMPORAL_STALENESS,
            ],
            "BOUNDARY_AND_ABSTRACTION": [
                cls.BOUNDARY_VIOLATION,
                cls.ABSTRACTION_WRONG,
                cls.BOUNDARY_LEAK,
                cls.SCALAR_COLLAPSE,
            ],
            "HUMAN_AND_COGNITIVE": [
                cls.HUMAN_FATIGUE,
                cls.HUMAN_RUBBER_STAMP,
                cls.EPISTEMIC_OVERCONFIDENCE,
                cls.COGNITIVE_FRAMING,
                cls.HUMAN_BOTTLENECK,
            ],
            "OBSERVABILITY_AND_TRUTH": [
                cls.FALSE_CAUSALITY,
                cls.NARRATIVE_FRAGILITY,
                cls.INVISIBLE_FAILURE,
                cls.OBSERVABILITY_GAP,
            ],
            "AMBIGUITY_AND_INTENT": [
                cls.INTENT_AMBIGUITY,
                cls.FALLTHROUGH_FAILURE,
                cls.INTENT_EXHAUSTION,
            ],
            "META_GOVERNANCE": [
                cls.META_AUTHORITY,
                cls.GOVERNANCE_DRIFT,
                cls.POLICY_CEREMONIALITY,
            ],
            "SCALING_AND_COMPLEXITY": [
                cls.SCALING_OVERFLOW,
                cls.COMPLEXITY_EXPLOSION,
                cls.FRAGMENTATION,
            ],
            "SAFETY_AND_RISK": [
                cls.OVER_SAFETY_AVERSION,
                cls.FAIL_OPEN_PRESSURE,
                cls.RISK_TUNING_SENSITIVITY,
            ],
            "STRUCTURAL_AND_ARCHITECTURAL": [
                cls.ABOUNDED_EXECUTION,
                cls.IMPACT_VS_COUNT_ERROR,
                cls.REALITY_MISMATCH,
            ],
        }
        return categories


# Explicit export of taxonomy
FAILURE_TAXONOMY = {
    "name": "AIOS Failure Taxonomy v1.0",
    "version": "1.0",
    "total_types": len(FailureType),
    "categories": list(FailureType.by_category().keys()),
    "types": [f.name for f in FailureType],
}
