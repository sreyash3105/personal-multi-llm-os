"""
MEK-5: Failure Primitives

Failure is composable, explicit, and truthful.
Failure is data, not UX.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Phase(Enum):
    """
    Execution phase where failure occurred.
    """

    MEK_0 = "mek_0"
    MEK_1 = "mek_1"
    MEK_2 = "mek_2"
    MEK_3 = "mek_3"
    MEK_4 = "mek_4"
    MEK_5 = "mek_5"


class FailureType(Enum):
    """
    Type of failure.

    Closed enum - no new types allowed.
    """

    # Context failures
    MISSING_CONTEXT = "missing_context"
    INVALID_CONTEXT = "invalid_context"
    CONTEXT_IMMUTABILITY_VIOLATION = "context_immutability_violation"

    # Intent failures
    MISSING_INTENT = "missing_intent"
    INVALID_INTENT = "invalid_intent"
    INTENT_INFERENCE_ATTEMPT = "intent_inference_attempt"

    # Confidence failures
    MISSING_CONFIDENCE = "missing_confidence"
    INVALID_CONFIDENCE = "invalid_confidence"
    CONFIDENCE_THRESHOLD_EXCEEDED = "confidence_threshold_exceeded"

    # Principal failures
    MISSING_PRINCIPAL = "missing_principal"
    UNKNOWN_PRINCIPAL = "unknown_principal"

    # Grant failures
    MISSING_GRANT = "missing_grant"
    EXPIRED_GRANT = "expired_grant"
    REVOKED_GRANT = "revoked_grant"
    EXHAUSTED_GRANT = "exhausted_grant"
    INVALID_GRANT_SCOPE = "invalid_grant_scope"

    # Capability failures
    UNKNOWN_CAPABILITY = "unknown_capability"
    CAPABILITY_SELF_INVOCATION = "capability_self_invocation"

    # Authority failures
    UNIFIED_EXECUTION_AUTHORITY_VIOLATION = "unified_execution_authority_violation"
    DIRECT_EXECUTION_ATTEMPT = "direct_execution_attempt"

    # Friction failures
    FRICTION_VIOLATION = "friction_violation"
    CONSEQUENCE_LEVEL_MISMATCH = "consequence_level_mismatch"

    # Snapshot failures
    SNAPSHOT_HASH_MISMATCH = "snapshot_hash_mismatch"
    SNAPSHOT_REUSE_ATTEMPT = "snapshot_reuse_attempt"
    TOCTOU_VIOLATION = "toctou_violation"

    # Composition failures
    COMPOSITION_STEP_FAILURE = "composition_step_failure"
    COMPOSITION_ORDER_VIOLATION = "composition_order_violation"

    # Execution failures
    EXECUTION_ERROR = "execution_error"
    GUARD_REFUSAL = "guard_refusal"


class Invariant(Enum):
    """
    Violated invariant.

    Closed enum - no new invariants allowed.
    """

    I1_UNIFIED_EXECUTION_AUTHORITY = "i1_unified_execution_authority"
    I2_CONFIDENCE_BEFORE_ACTION = "i2_confidence_before_action"
    I3_FRICTION_UNDER_CONSEQUENCE = "i3_friction_under_consequence"
    I4_REFUSAL_IS_TERMINAL = "i4_refusal_is_terminal"
    I5_NON_ACTION_MUST_SURFACE = "i5_non_action_must_surface"
    I6_PATTERNS_OBSERVE_NEVER_CONTROL = "i6_patterns_observe_never_control"
    I7_NEGATIVE_CAPABILITY = "i7_negative_capability"


@dataclass(frozen=True)
class FailureEvent:
    """
    Immutable, structured, terminal failure event.

    Fields:
        failure_id: Unique identifier
        phase: Execution phase (MEK-0...MEK-5)
        step_id: Optional step identifier (for compositions)
        failure_type: Type of failure (closed enum)
        violated_invariant: Invariant that was violated (if applicable)
        triggering_condition: Exact condition that triggered failure (no paraphrase)
        authority_context: Authority context (principal_id, grant_id)
        snapshot_id: Snapshot ID (if applicable)
        timestamp: Monotonic timestamp

    Rules:
        - FailureType enum is closed
        - No free-text explanation
        - No LLM-generated content
        - Missing fields → refusal
    """

    failure_id: str
    phase: Phase
    failure_type: FailureType
    triggering_condition: str
    timestamp: int
    step_id: Optional[str] = None
    violated_invariant: Optional[Invariant] = None
    authority_context: Optional[Dict[str, Any]] = None
    snapshot_id: Optional[str] = None

    def __post_init__(self):
        """
        Validate failure event after creation.

        Raises ValueError if invalid.
        """
        if not self.failure_id:
            raise ValueError("failure_id is required")

        if not self.triggering_condition:
            raise ValueError("triggering_condition is required")

        if self.timestamp is None:
            raise ValueError("timestamp is required")


@dataclass(frozen=True)
class FailureComposition:
    """
    Ordered list of Failure Events.

    Rules:
        - Preserves order of occurrence
        - No deduplication
        - No summarization
        - No "root cause" inference
        - No severity ranking
        - No collapsing
    """

    composition_id: str
    failures: List[FailureEvent]

    def __post_init__(self):
        """
        Validate failure composition after creation.

        Raises ValueError if invalid.
        """
        if not self.composition_id:
            raise ValueError("composition_id is required")

        if not self.failures:
            raise ValueError("failures is required")

        # Validate order is preserved
        for i in range(len(self.failures) - 1):
            if self.failures[i].timestamp > self.failures[i + 1].timestamp:
                raise ValueError(
                    f"Failures out of order at index {i}: "
                    f"timestamp {self.failures[i].timestamp} > "
                    f"{self.failures[i + 1].timestamp}"
                )


@dataclass(frozen=True)
class FailureResult:
    """
    Final output when execution halts due to failure.

    Fields:
        composition_id: Composition ID (if applicable)
        failures: Ordered Failure Events
        terminal: Always True (for failure results)

    No success metadata allowed.
    """

    composition_id: Optional[str]
    failures: List[FailureEvent]
    terminal: bool = True

    def __post_init__(self):
        """
        Validate failure result after creation.

        Raises ValueError if invalid.
        """
        if not self.failures:
            raise ValueError("failures is required")

        if not self.terminal:
            raise ValueError("terminal must be True for failure results")


def create_failure_event(
    failure_id: str,
    phase: Phase,
    failure_type: FailureType,
    triggering_condition: str,
    timestamp: Optional[int] = None,
    step_id: Optional[str] = None,
    violated_invariant: Optional[Invariant] = None,
    principal_id: Optional[str] = None,
    grant_id: Optional[str] = None,
    snapshot_id: Optional[str] = None,
) -> FailureEvent:
    """
    Create a failure event.

    Validates input before creation.
    """
    import time

    if timestamp is None:
        timestamp = int(time.time() * 1000)

    authority_context = None
    if principal_id is not None or grant_id is not None:
        authority_context = {}
        if principal_id is not None:
            authority_context["principal_id"] = principal_id
        if grant_id is not None:
            authority_context["grant_id"] = grant_id

    return FailureEvent(
        failure_id=failure_id,
        phase=phase,
        failure_type=failure_type,
        triggering_condition=triggering_condition,
        timestamp=timestamp,
        step_id=step_id,
        violated_invariant=violated_invariant,
        authority_context=authority_context,
        snapshot_id=snapshot_id,
    )


def create_failure_composition(
    composition_id: str,
    failures: List[FailureEvent]
) -> FailureComposition:
    """
    Create a failure composition.

    Validates composition before creation.
    """
    if not composition_id:
        raise ValueError("composition_id is required")

    if not failures:
        raise ValueError("failures is required")

    return FailureComposition(
        composition_id=composition_id,
        failures=failures,
    )


def create_failure_result(
    composition_id: Optional[str],
    failures: List[FailureEvent]
) -> FailureResult:
    """
    Create a failure result.

    Validates result before creation.
    """
    if not failures:
        raise ValueError("failures is required")

    return FailureResult(
        composition_id=composition_id,
        failures=failures,
        terminal=True,
    )
