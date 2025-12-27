"""
MEK-4: Composition Without Power

Mechanical composition without emergent authority.
Each step is independent. No shared power.
"""

from typing import Any

from composition_primitives import (
    Step,
    Composition,
    FailurePolicy,
    StepResult,
    CompositionResult,
    create_step,
    create_composition,
    create_success_result,
    create_refusal_result,
)
from composition_guard import CompositionGuard, get_composition_guard


__all__ = [
    # Primitives
    "Step",
    "Composition",
    "FailurePolicy",
    "StepResult",
    "CompositionResult",
    # Factory functions
    "create_step",
    "create_composition",
    "create_success_result",
    "create_refusal_result",
    # Guard
    "CompositionGuard",
    "get_composition_guard",
]


def execute_composition(
    guard: Any,
    composition: Composition
) -> CompositionResult:
    """
    Execute composition through Guard.

    Args:
        guard: MEK SnapshotAuthorityGuard
        composition: Composition to execute

    Returns:
        CompositionResult with success or refusal
    """
    comp_guard = get_composition_guard(guard)
    return comp_guard.execute_composition(composition)
