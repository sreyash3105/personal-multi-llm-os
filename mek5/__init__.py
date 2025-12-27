"""
MEK-5: Failure as First-Class Output

Failure is composable, explicit, and truthful.
Failure is data, not UX.
"""

from typing import Any

from failure_primitives import (
    Phase,
    FailureType,
    Invariant,
    FailureEvent,
    FailureComposition,
    FailureResult,
    create_failure_event,
    create_failure_composition,
    create_failure_result,
)
from failure_guard import FailureGuard, get_failure_guard


__all__ = [
    # Enums
    "Phase",
    "FailureType",
    "Invariant",
    # Primitives
    "FailureEvent",
    "FailureComposition",
    "FailureResult",
    # Factory functions
    "create_failure_event",
    "create_failure_composition",
    "create_failure_result",
    # Guard
    "FailureGuard",
    "get_failure_guard",
]


def track_failure(
    guard: Any,
    capability_name: str,
    context: dict,
    phase: Phase = Phase.MEK_3,
    step_id: str = None,  # type: ignore
) -> dict:
    """
    Track failure during execution.

    Args:
        guard: MEK SnapshotAuthorityGuard
        capability_name: Capability to execute
        context: Execution context
        phase: MEK phase
        step_id: Optional step ID

    Returns:
        Execution result or failure result
    """
    fail_guard = get_failure_guard(guard)
    return fail_guard.execute_with_failure_tracking(
        capability_name=capability_name,
        context=context,
        phase=phase,
        step_id=step_id,
    )
