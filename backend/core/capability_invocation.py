"""
Unified capability invocation path.

All execution flows through this single path.

INVARIANT 1: UNIFIED EXECUTION AUTHORITY
All capability execution MUST pass through ExecutionGuard.
Direct calls to capability.execute() are structurally impossible.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
from backend.core.capability import CapabilityDescriptor, create_refusal, RefusalReason
from backend.core.capability_registry import get_capability, list_capabilities
from backend.core.context_manager import ExecutionContext
from backend.core.config import (
    PERCEPTION_CONFIRM_REQUIRED,
    PERCEPTION_CONFIDENCE_LOW_THRESHOLD,
    PERCEPTION_CONFIDENCE_MEDIUM_THRESHOLD,
    PERCEPTION_CONFIDENCE_HIGH_THRESHOLD,
)


def apply_friction_if_required(
    capability: CapabilityDescriptor,
    confidence: Optional[float],
    context: Dict[str, Any],
) -> None:
    """
    DEPRECATED: Friction is now handled by ExecutionGuard.

    INVARIANT 3: FRICTION UNDER CONSEQUENCE
    - Friction is enforced by ExecutionGuard.execute_capability()
    - This method is kept for compatibility but does nothing
    - All friction logic is in ExecutionGuard
    """
    pass


def record_capability_invocation(
    capability: CapabilityDescriptor,
    context: ExecutionContext,
    result: Any,
    refusal_reason: Optional[str] = None,
) -> None:
    """
    DEPRECATED: Pattern recording is now handled by ExecutionGuard.

    INVARIANT 6: PATTERNS OBSERVE, NEVER CONTROL
    - Pattern aggregation is handled by ExecutionGuard.execute_capability()
    - This method is kept for compatibility but does nothing
    - All pattern logic is in ExecutionGuard
    """
    pass


def invoke_capability(
    capability_name: str,
    context: Dict[str, Any],
) -> Any:
    """
    Unified entry point for all capability invocations.

    INVARIANT 1: UNIFIED EXECUTION AUTHORITY
    - All capability execution MUST pass through ExecutionGuard
    - Direct calls to capability.execute() are structurally impossible

    INVARIANT 2: CONFIDENCE BEFORE ACTION
    - Confidence is mandatory in context
    - No default confidence allowed

    Flow:
    1. Get capability from registry
    2. Pass to ExecutionGuard for execution with full invariant enforcement
    3. Return result (success or refusal)
    """
    capability = get_capability(capability_name)
    if not capability:
        return create_refusal(
            RefusalReason.SCOPE_VIOLATION,
            f"Unknown capability: {capability_name}",
            capability_name,
        )

    execution_context = context.get("execution_context")
    if not execution_context:
        execution_context = context
        context["execution_context"] = execution_context

    from backend.core.execution_guard import get_execution_guard
    guard = get_execution_guard()

    return guard.execute_capability(
        capability=capability,
        context=context,
        execution_context=execution_context,
    )


def invoke_capability_with_confirmation(
    capability_name: str,
    context: Dict[str, Any],
    confirmations: Dict[str, bool],
) -> Any:
    """
    Invoke capability with explicit confirmations.

    confirmations maps scope/approval_name to bool.
    """
    context["approvals"] = [
        key for key, confirmed in confirmations.items() if confirmed
    ]
    return invoke_capability(capability_name, context)


def list_all_capabilities() -> List[Dict[str, Any]]:
    """
    List all capabilities with metadata.
    """
    caps = list_capabilities()
    return [
        {
            "name": cap.name,
            "scope": cap.scope,
            "consequence_level": cap.consequence_level.value,
            "required_context_fields": cap.required_context_fields,
            "required_approvals": cap.required_approvals,
        }
        for cap in caps
    ]
