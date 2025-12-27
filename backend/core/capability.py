"""
Capability kernel interface.

Defines how all power enters AIOS system.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, Dict, Any, List, Optional, Set
from abc import ABC, abstractmethod


class ConsequenceLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CapabilityDescriptor:
    """
    Describes a capability with explicit constraints.
    """

    def __init__(
        self,
        name: str,
        scope: str,
        consequence_level: ConsequenceLevel,
        required_context_fields: List[str],
        required_approvals: Optional[List[str]] = None,
        execute_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self.name = name
        self.scope = scope
        self.consequence_level = consequence_level
        self.required_context_fields = required_context_fields
        self.required_approvals = required_approvals or []
        self.execute_fn = execute_fn

    def validate_context(self, context: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate that context contains all required fields.
        Returns (is_valid, missing_fields).
        """
        missing = []
        for field in self.required_context_fields:
            if field not in context or context[field] is None:
                missing.append(field)
        return len(missing) == 0, missing

    def execute(self, context: Dict[str, Any]) -> Any:
        """
        EXECUTE IS DISABLED.

        INVARIANT 1: UNIFIED EXECUTION AUTHORITY
        No capability may execute outside the unified invocation path.
        Direct calls to Capability.execute() MUST raise an error.
        Only the kernel runner may invoke execution.

        Use ExecutionGuard.execute_capability() instead.
        """
        raise RuntimeError(
            f"INVARIANT_1_VIOLATION: Direct execution of capability '{self.name}' is forbidden. "
            "All capability execution MUST pass through ExecutionGuard.execute_capability(). "
            "This is a structural invariant - do not bypass."
        )


class RefusalReason(Enum):
    MISSING_CONTEXT = "missing_context"
    MISSING_APPROVAL = "missing_approval"
    SCOPE_VIOLATION = "scope_violation"
    CONSTRAINT_VIOLATION = "constraint_violation"
    AMBIGUITY = "ambiguity"


def create_refusal(
    reason: RefusalReason,
    explanation: str,
    capability: str,
    source_confidence: Optional[float] = None,
    alternatives: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Create structured refusal response.

    Returns dict with:
    - status: "refused"
    - reason: RefusalReason value
    - explanation: human-readable explanation
    - capability: name of capability
    - source_confidence: confidence that triggered refusal (if applicable)
    - alternatives: suggested alternatives (if any)
    """
    return {
        "status": "refused",
        "reason": reason.value,
        "explanation": explanation,
        "capability": capability,
        "source_confidence": source_confidence,
        "alternatives": alternatives or [],
    }
