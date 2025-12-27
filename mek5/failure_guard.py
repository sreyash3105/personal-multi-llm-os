"""
MEK-5: Failure Guard Extension

Extends Guard to create Failure Events on refusals.
Failure is data, not UX.
"""

import time
import uuid
from typing import Any, Dict, List, Optional

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


class FailureGuard:
    """
    Guard extension for failure handling.

    Creates Failure Events on refusals.
    Preserves failures as data.
    """

    def __init__(self, guard: Any):
        """
        Initialize with MEK Guard.

        Args:
            guard: MEK SnapshotAuthorityGuard from MEK-3
        """
        self.guard = guard
        self.current_failures: List[FailureEvent] = []

    def execute_with_failure_tracking(
        self,
        capability_name: str,
        context: Dict[str, Any],
        phase: Phase = Phase.MEK_3,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute capability with failure tracking.

        Creates Failure Event on refusal.
        Appends to current failure composition.

        Args:
            capability_name: Capability to execute
            context: Execution context
            phase: MEK phase
            step_id: Optional step ID (for compositions)

        Returns:
            Execution result or failure result
        """
        try:
            mek_result = self.guard.execute(
                capability_name=capability_name,
                context=context,
            )

            if mek_result.get("is_success", False):
                return mek_result
            else:
                non_action = mek_result.get("non_action", {})
                failure = self._create_failure_from_non_action(
                    non_action=non_action,
                    phase=phase,
                    step_id=step_id,
                    context=context,
                )

                self.current_failures.append(failure)

                return {
                    "is_success": False,
                    "failure": failure,
                    "non_action": non_action,
                }
        except Exception as e:
            failure = create_failure_event(
                failure_id=str(uuid.uuid4()),
                phase=phase,
                failure_type=FailureType.EXECUTION_ERROR,
                triggering_condition=str(e),
                step_id=step_id,
            )

            self.current_failures.append(failure)

            return {
                "is_success": False,
                "failure": failure,
                "non_action": {
                    "reason": "EXECUTION_ERROR",
                    "details": {"error": str(e)},
                    "timestamp": int(time.time()),
                },
            }

    def _create_failure_from_non_action(
        self,
        non_action: Dict[str, Any],
        phase: Phase,
        step_id: Optional[str],
        context: Dict[str, Any],
    ) -> FailureEvent:
        """
        Create Failure Event from Non-Action.

        Maps Non-Action reasons to Failure Types.
        """
        reason = non_action.get("reason", "UNKNOWN")

        failure_type_map = {
            "MISSING_CONFIDENCE": FailureType.MISSING_CONFIDENCE,
            "INVALID_CONFIDENCE": FailureType.INVALID_CONFIDENCE,
            "MISSING_PRINCIPAL": FailureType.MISSING_PRINCIPAL,
            "UNKNOWN_PRINCIPAL": FailureType.UNKNOWN_PRINCIPAL,
            "NO_GRANT": FailureType.MISSING_GRANT,
            "EXPIRED_GRANT": FailureType.EXPIRED_GRANT,
            "REVOKED_GRANT": FailureType.REVOKED_GRANT,
            "EXHAUSTED_GRANT": FailureType.EXHAUSTED_GRANT,
            "UNKNOWN_CAPABILITY": FailureType.UNKNOWN_CAPABILITY,
            "INVALID_GRANT_SCOPE": FailureType.INVALID_GRANT_SCOPE,
            "SNAPSHOT_HASH_MISMATCH": FailureType.SNAPSHOT_HASH_MISMATCH,
            "SNAPSHOT_REUSE_ATTEMPT": FailureType.SNAPSHOT_REUSE_ATTEMPT,
            "TOCTOU_VIOLATION": FailureType.TOCOU_VIOLATION,
            "COMPOSITION_STEP_FAILURE": FailureType.COMPOSITION_STEP_FAILURE,
        }

        failure_type = failure_type_map.get(reason, FailureType.GUARD_REFUSAL)

        return create_failure_event(
            failure_id=str(uuid.uuid4()),
            phase=phase,
            failure_type=failure_type,
            triggering_condition=f"Non-Action reason: {reason}",
            step_id=step_id,
            principal_id=context.get("principal_id"),
            grant_id=context.get("grant_id"),
            snapshot_id=context.get("snapshot_id"),
        )

    def get_failure_composition(
        self,
        composition_id: Optional[str] = None
    ) -> FailureComposition:
        """
        Get current failure composition.

        Returns ordered Failure Events.
        """
        if not self.current_failures:
            raise ValueError("No failures to compose")

        return create_failure_composition(
            composition_id=composition_id or str(uuid.uuid4()),
            failures=list(self.current_failures),
        )

    def get_failure_result(
        self,
        composition_id: Optional[str] = None
    ) -> FailureResult:
        """
        Get failure result.

        Returns FailureResult with current failures.
        """
        if not self.current_failures:
            raise ValueError("No failures to report")

        return create_failure_result(
            composition_id=composition_id,
            failures=list(self.current_failures),
        )

    def clear_failures(self) -> None:
        """
        Clear current failures.

        Called between independent executions.
        """
        self.current_failures.clear()

    def has_failures(self) -> bool:
        """
        Check if there are failures.
        """
        return len(self.current_failures) > 0


def get_failure_guard(guard: Any) -> FailureGuard:
    """
    Get failure guard instance.

    Args:
        guard: MEK SnapshotAuthorityGuard

    Returns:
        FailureGuard instance
    """
    return FailureGuard(guard)
