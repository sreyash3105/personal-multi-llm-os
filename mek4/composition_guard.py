"""
MEK-4: Composition Guard

Executes compositions step-by-step through Guard.
Each step passes independently through Guard.
No shared authority. No shared snapshot.
"""

from typing import Any, Dict, List, Optional

from composition_primitives import (
    Composition,
    CompositionResult,
    Step,
    StepResult,
    create_success_result,
    create_refusal_result,
)


class CompositionGuard:
    """
    Guard for composition execution.

    Executes compositions step-by-step.
    Each step passes independently through Guard.

    Rules:
        - Each step has independent Context
        - Each step has independent Intent
        - Each step has independent Snapshot
        - Each step passes independently through Guard
        - First refusal halts entire composition (STRICT policy)
        - No partial success exposure
    """

    def __init__(self, guard: Any):
        """
        Initialize with MEK Guard.

        Args:
            guard: MEK SnapshotAuthorityGuard from MEK-3
        """
        self.guard = guard

    def execute_composition(
        self,
        composition: Composition
    ) -> CompositionResult:
        """
        Execute composition.

        Executes steps in order.
        First refusal halts entire composition.

        Args:
            composition: Composition to execute

        Returns:
            CompositionResult with success or refusal
        """
        step_results: List[StepResult] = []

        for step in composition.steps:
            step_result = self._execute_step(step)
            step_results.append(step_result)

            if not step_result.is_success:
                return CompositionResult(
                    composition_id=composition.composition_id,
                    is_success=False,
                    steps=step_results,
                    non_action=step_result.non_action,
                    halted_at_step=step.step_id,
                )

        return CompositionResult(
            composition_id=composition.composition_id,
            is_success=True,
            steps=step_results,
            final_data=step_results[-1].data if step_results else None,
        )

    def _execute_step(self, step: Step) -> StepResult:
        """
        Execute single step through Guard.

        Each step:
            1. Validates step Context
            2. Validates step Intent
            3. Validates Principal
            4. Validates Grant
            5. Validates Snapshot
            6. Applies Confidence gate
            7. Applies Friction
            8. Executes OR Refuses

        Args:
            step: Step to execute

        Returns:
            StepResult with success or refusal
        """
        try:
            mek_result = self.guard.execute(
                capability_name=step.capability_name,
                context=step.context,
            )

            if mek_result.get("is_success", False):
                return create_success_result(
                    step_id=step.step_id,
                    order=step.order,
                    data=mek_result.get("data", {}),
                    snapshot_id=mek_result.get("snapshot_id"),
                )
            else:
                return create_refusal_result(
                    step_id=step.step_id,
                    order=step.order,
                    non_action=mek_result.get("non_action", {}),
                )
        except Exception as e:
            return create_refusal_result(
                step_id=step.step_id,
                order=step.order,
                non_action={
                    "reason": "EXECUTION_ERROR",
                    "details": {"error": str(e)},
                    "timestamp": None,
                },
            )


def get_composition_guard(guard: Any) -> CompositionGuard:
    """
    Get composition guard instance.

    Args:
        guard: MEK SnapshotAuthorityGuard

    Returns:
        CompositionGuard instance
    """
    return CompositionGuard(guard)
