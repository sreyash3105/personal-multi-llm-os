"""
MEK-4: Composition Primitives

Mechanical composition without emergent authority.
Each step is independent. No shared power.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FailurePolicy(Enum):
    """
    Failure policy for composition.

    STRICT ONLY - no other policies allowed.
    """

    STRICT = "strict"

    def __init__(self, value: str):
        if value != "strict":
            raise ValueError(f"Only STRICT policy is allowed, got: {value}")


@dataclass(frozen=True)
class Step:
    """
    Single step in composition.

    Each step has:
    - Its own Context
    - Its own Intent
    - Its own Snapshot (created during execution)
    - Independent Guard checks

    No shared authority.
    No shared snapshot.
    No shared confidence.
    """

    step_id: str
    capability_name: str
    context: Dict[str, Any]
    order: int


@dataclass(frozen=True)
class Composition:
    """
    Composition Contract.

    An ordered list of independent executions.

    Fields:
        composition_id: Unique identifier
        steps: Ordered list of steps (explicit, no reordering)
        failure_policy: STRICT only (no other policies)

    Rules:
        - STRICT failure policy = first refusal halts entire composition
        - No retries
        - No branching
        - No conditional logic
        - No shared authority between steps
    """

    composition_id: str
    steps: List[Step]
    failure_policy: FailurePolicy = field(default=FailurePolicy.STRICT)

    def __post_init__(self):
        """
        Validate composition after creation.

        Raises ValueError if invalid.
        """
        if not self.steps:
            raise ValueError("Composition must have at least one step")

        if self.failure_policy != FailurePolicy.STRICT:
            raise ValueError("Only STRICT failure policy is allowed")

        # Validate step ordering
        for i, step in enumerate(self.steps):
            if step.order != i:
                raise ValueError(
                    f"Step order mismatch at index {i}: "
                    f"expected {i}, got {step.order}"
                )


@dataclass(frozen=True)
class StepResult:
    """
    Result of single step execution.

    Either:
    - Success (Result + snapshot_id)
    - Refusal (Non-Action)

    No partial success.
    No aggregation.
    """

    step_id: str
    order: int
    is_success: bool
    data: Optional[Dict[str, Any]] = None
    snapshot_id: Optional[str] = None
    non_action: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class CompositionResult:
    """
    Result of composition execution.

    If all steps succeed:
        - is_success = True
        - final_data = last step's data
        - steps = all step results

    If any step refuses:
        - is_success = False
        - non_action = first refusal's non-action
        - steps = executed steps up to refusal
        - halted_at_step = step that caused refusal

    No partial success exposure.
    No aggregation of outputs.
    """

    composition_id: str
    is_success: bool
    steps: List[StepResult]
    final_data: Optional[Dict[str, Any]] = None
    non_action: Optional[Dict[str, Any]] = None
    halted_at_step: Optional[str] = None


def create_step(
    step_id: str,
    capability_name: str,
    context: Dict[str, Any],
    order: int
) -> Step:
    """
    Create a step.

    Validates input before creation.
    """
    if not step_id:
        raise ValueError("step_id is required")

    if not capability_name:
        raise ValueError("capability_name is required")

    if order < 0:
        raise ValueError(f"order must be >= 0, got: {order}")

    if not isinstance(context, dict):
        raise ValueError("context must be a dict")

    return Step(
        step_id=step_id,
        capability_name=capability_name,
        context=context,
        order=order,
    )


def create_composition(
    composition_id: str,
    steps: List[Dict[str, Any]]
) -> Composition:
    """
    Create a composition from step definitions.

    Converts step dicts to Step objects.
    Validates composition contract.
    """
    if not composition_id:
        raise ValueError("composition_id is required")

    if not steps:
        raise ValueError("steps is required")

    step_objects = [
        create_step(
            step_id=step["step_id"],
            capability_name=step["capability_name"],
            context=step["context"],
            order=step["order"],
        )
        for step in steps
    ]

    return Composition(
        composition_id=composition_id,
        steps=step_objects,
        failure_policy=FailurePolicy.STRICT,
    )


def create_success_result(
    step_id: str,
    order: int,
    data: Dict[str, Any],
    snapshot_id: str
) -> StepResult:
    """
    Create successful step result.
    """
    return StepResult(
        step_id=step_id,
        order=order,
        is_success=True,
        data=data,
        snapshot_id=snapshot_id,
    )


def create_refusal_result(
    step_id: str,
    order: int,
    non_action: Dict[str, Any]
) -> StepResult:
    """
    Create refusal step result.
    """
    return StepResult(
        step_id=step_id,
        order=order,
        is_success=False,
        non_action=non_action,
    )
