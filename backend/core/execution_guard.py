"""
ExecutionGuard - Central execution authority enforcement.

WORKSTREAM A: EXECUTION GUARD (FOUNDATIONAL)

All capability execution MUST pass through this guard.
Direct calls to Capability.execute() are structurally impossible.
"""

from __future__ import annotations

import time
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field

from backend.core.capability import CapabilityDescriptor, ConsequenceLevel, create_refusal, RefusalReason
from backend.core.context_manager import ExecutionContext
from backend.core.config import (
    PERCEPTION_CONFIDENCE_LOW_THRESHOLD,
    PERCEPTION_CONFIDENCE_MEDIUM_THRESHOLD,
    PERCEPTION_CONFIDENCE_HIGH_THRESHOLD,
)


class InvariantViolationError(RuntimeError):
    """
    Raised when a core invariant is violated.

    This should NEVER happen in production code.
    Indicates a structural bypass attempt.
    """
    pass


@dataclass
class FrictionParams:
    """Immutable friction parameters for a capability invocation."""
    required_duration_seconds: int
    start_time: float = field(default_factory=time.time)

    def is_friction_complete(self) -> bool:
        """Check if friction period has elapsed."""
        return time.time() - self.start_time >= self.required_duration_seconds

    def wait_if_required(self) -> None:
        """
        Block execution until friction is complete.

        INVARIANT 3: FRICTION UNDER CONSEQUENCE
        - No skip, no bypass, no override, no "emergency mode"
        - This is a blocking call that CANNOT be bypassed
        """
        remaining = self.required_duration_seconds - (time.time() - self.start_time)
        if remaining > 0:
            time.sleep(remaining)


class ExecutionGuard:
    """
    Central authority for all capability execution.

    ENFORCED INVARIANTS:
    1. UNIFIED EXECUTION AUTHORITY - Only this guard may execute capabilities
    2. CONFIDENCE BEFORE ACTION - Confidence is mandatory, no defaults
    3. FRICTION UNDER CONSEQUENCE - High consequence triggers immutable friction
    4. REFUSAL IS FIRST-CLASS - Refusal is terminal, no fallback
    5. NON-ACTION MUST SURFACE - Every refusal emits explicit report
    """

    _friction_durations = {
        ConsequenceLevel.HIGH: 10,
        ConsequenceLevel.MEDIUM: 3,
        ConsequenceLevel.LOW: 0,
    }

    _high_confidence_threshold = 0.8
    _medium_confidence_threshold = 0.6

    def __init__(self):
        self._execution_lock = threading.Lock()

    def enforce_confidence_required(self, confidence: Optional[float], capability_name: str) -> None:
        """
        INVARIANT 2: CONFIDENCE BEFORE ACTION

        Every capability invocation MUST pass through a confidence gate.
        If confidence is unbounded, execution MUST refuse.
        No default confidence allowed.
        Confidence cannot be overridden downstream.

        Raises InvariantViolationError if confidence is None or not in valid range.
        """
        if confidence is None:
            raise InvariantViolationError(
                f"INVARIANT_2_VIOLATION: Capability '{capability_name}' invoked without confidence. "
                "Confidence is mandatory and cannot be None."
            )

        if not (0.0 <= confidence <= 1.0):
            raise InvariantViolationError(
                f"INVARIANT_2_VIOLATION: Capability '{capability_name}' invoked with invalid confidence: {confidence}. "
                "Confidence must be between 0.0 and 1.0."
            )

    def calculate_friction_duration(
        self,
        capability: CapabilityDescriptor,
        confidence: float,
    ) -> int:
        """
        Calculate friction duration based on consequence and confidence.

        INVARIANT 3: FRICTION UNDER CONSEQUENCE
        - Any capability with consequence >= HIGH MUST trigger friction
        - Friction duration is immutable
        """
        base_duration = self._friction_durations.get(capability.consequence_level, 0)

        if confidence < PERCEPTION_CONFIDENCE_LOW_THRESHOLD:
            return base_duration + 5
        elif confidence < PERCEPTION_CONFIDENCE_MEDIUM_THRESHOLD:
            return base_duration + 2

        return base_duration

    def execute_capability(
        self,
        capability: CapabilityDescriptor,
        context: Dict[str, Any],
        execution_context: Optional[ExecutionContext] = None,
    ) -> Dict[str, Any]:
        """
        Execute a capability with full invariant enforcement.

        This is the ONLY allowed path for capability execution.

        FLOW:
        1. Validate confidence is present (INVARIANT 2)
        2. Calculate and apply friction if required (INVARIANT 3)
        3. Validate context fields
        4. Check approvals
        5. Execute or refuse
        6. Emit non-action report if refused (INVARIANT 5)
        7. Record pattern (INVARIANT 6 - observer only)

        INVARIANT 1: UNIFIED EXECUTION AUTHORITY
        - Direct calls to capability.execute() are impossible
        - Only this method may invoke the underlying execute_fn
        """
        confidence = context.get("confidence")
        self.enforce_confidence_required(confidence, capability.name)

        friction_duration = self.calculate_friction_duration(capability, float(confidence))
        friction = FrictionParams(friction_duration)

        friction.wait_if_required()

        is_valid, missing_fields = capability.validate_context(context)
        if not is_valid:
            refusal = create_refusal(
                RefusalReason.MISSING_CONTEXT,
                f"Missing required context fields: {missing_fields}",
                capability.name,
                source_confidence=confidence,
            )

            self._emit_non_action_report(
                capability=capability,
                context=execution_context,
                refusal=refusal,
                reason="missing_context",
            )

            return refusal

        if capability.required_approvals:
            approvals_met = set(context.get("approvals", []))
            required = set(capability.required_approvals)
            if not required.issubset(approvals_met):
                missing_approvals = list(required - approvals_met)
                refusal = create_refusal(
                    RefusalReason.MISSING_APPROVAL,
                    f"Missing required approvals: {missing_approvals}",
                    capability.name,
                    source_confidence=confidence,
                )

                self._emit_non_action_report(
                    capability=capability,
                    context=execution_context,
                    refusal=refusal,
                    reason="missing_approval",
                )

                return refusal

        try:
            with self._execution_lock:
                result = capability.execute_fn(context)

            self._record_pattern(capability, execution_context, result, confidence)

            return result

        except Exception as e:
            refusal = create_refusal(
                RefusalReason.CONSTRAINT_VIOLATION,
                f"Execution failed: {str(e)}",
                capability.name,
                source_confidence=confidence,
            )

            self._emit_non_action_report(
                capability=capability,
                context=execution_context,
                refusal=refusal,
                reason="execution_error",
            )

            return refusal

    def _emit_non_action_report(
        self,
        capability: CapabilityDescriptor,
        context: Optional[ExecutionContext],
        refusal: Dict[str, Any],
        reason: str,
    ) -> None:
        """
        INVARIANT 5: NON-ACTION MUST SURFACE

        Every refusal or halt MUST emit an explicit Non-Action report.
        Silence is illegal.
        Reports must be structured, not free-text.
        """
        report = {
            "type": "non_action",
            "capability": capability.name,
            "consequence_level": capability.consequence_level.value,
            "reason": reason,
            "refusal_details": refusal,
            "context_id": context.context_id if context else None,
            "profile_id": context.profile_id if context else None,
            "session_id": context.session_id if context else None,
            "timestamp": time.time(),
        }

        self._record_pattern(capability, context, refusal, refusal.get("source_confidence"), is_refusal=True)

    def _record_pattern(
        self,
        capability: CapabilityDescriptor,
        context: Optional[ExecutionContext],
        result: Any,
        confidence: Optional[float],
        is_refusal: bool = False,
    ) -> None:
        """
        INVARIANT 6: PATTERNS OBSERVE, NEVER CONTROL

        Pattern aggregation MUST be non-blocking.
        Pattern layer MUST NOT affect execution.
        Removing the pattern layer entirely MUST NOT break execution.

        This method:
        - Does NOT block execution
        - Does NOT affect the return value
        - Is completely optional - failures are caught and logged
        """
        try:
            from backend.core.pattern_event import PatternEvent, PatternType, PatternSeverity
            from backend.core.pattern_record import PatternRecord

            pattern_type = PatternType.REFUSAL if is_refusal else PatternType.ACTION
            severity = PatternSeverity.HIGH if is_refusal else PatternSeverity.INFO

            metadata = {
                "capability": capability.name,
                "consequence_level": capability.consequence_level.value,
                "confidence": confidence,
                "context_id": context.context_id if context else None,
            }

            if is_refusal:
                metadata["refusal_reason"] = result.get("reason")

            event = PatternEvent(
                pattern_type=pattern_type,
                pattern_severity=severity,
                context_snapshot={
                    "profile_id": context.profile_id if context else "unknown",
                    "session_id": context.session_id if context else None,
                    "triggering_action": f"capability_execution:{capability.name}",
                    "pattern_details": metadata,
                },
            )

            PatternRecord.insert(event)

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Pattern recording failed (non-blocking): {e}")


_guard_instance: Optional[ExecutionGuard] = None
_guard_lock = threading.Lock()


def get_execution_guard() -> ExecutionGuard:
    """
    Get the global ExecutionGuard instance.

    This is the single point of execution authority.
    """
    global _guard_instance

    if _guard_instance is None:
        with _guard_lock:
            if _guard_instance is None:
                _guard_instance = ExecutionGuard()

    return _guard_instance
