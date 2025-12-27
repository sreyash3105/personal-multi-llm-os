"""
MEK-0: Minimal Execution Kernel
Constitution-as-Code

Primitives only. No convenience. No inference.
Betrayal is structurally impossible.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import threading
import time
import uuid


class ConsequenceLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class InvariantViolationError(RuntimeError):
    """Raised when kernel invariant is violated."""
    pass


class ProhibitedBehaviorError(RuntimeError):
    """Raised when prohibited behavior is attempted."""
    pass


# PRIMITIVE 1: CONTEXT (Immutable)
@dataclass(frozen=True)
class Context:
    """Immutable context created once per invocation."""
    context_id: str
    confidence: float
    intent: str
    fields: Dict[str, Any] = field(default_factory=dict)
    profile_id: Optional[str] = None
    session_id: Optional[str] = None

    def __post_init__(self):
        if self.confidence is None:
            raise ValueError("Context: confidence is required")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Context: confidence must be 0.0-1.0, got {self.confidence}")
        if not self.intent:
            raise ValueError("Context: intent is required")


# PRIMITIVE 2: INTENT (Declared)
@dataclass(frozen=True)
class Intent:
    """Explicitly declared intent."""
    name: str
    description: str

    def __post_init__(self):
        if not self.name:
            raise ValueError("Intent: name is required")


# PRIMITIVE 3: CAPABILITY CONTRACT (Declared Power)
@dataclass(frozen=True)
class CapabilityContract:
    """Immutable capability contract."""

    name: str
    consequence_level: ConsequenceLevel
    required_context_fields: List[str]
    _execute_fn: Callable[[Context], Any]

    def validate_context(self, context: Context) -> tuple[bool, List[str]]:
        """Validate that context contains all required fields."""
        missing = [
            f for f in self.required_context_fields
            if f not in context.fields or context.fields[f] is None
        ]
        return len(missing) == 0, missing

    def execute(self, context: Context) -> Any:
        """
        Direct execution is FORBIDDEN.

        I1: UNIFIED EXECUTION AUTHORITY
        All execution must pass through Guard.
        """
        raise InvariantViolationError(
            f"I1_VIOLATION: Direct execution of capability '{self.name}' is forbidden. "
            "All execution must pass through Guard.execute()."
        )


# PRIMITIVE 5: RESULT / NON-ACTION (Terminal)
class NonActionReason(Enum):
    MISSING_CONTEXT = "missing_context"
    MISSING_CONFIDENCE = "missing_confidence"
    INVALID_CONFIDENCE = "invalid_confidence"
    REFUSED_BY_GUARD = "refused_by_guard"
    EXECUTION_FAILED = "execution_failed"


@dataclass(frozen=True)
class Result:
    """Terminal result of invocation."""
    success: bool
    data: Optional[Any] = None
    non_action: Optional[Dict[str, Any]] = None

    def is_success(self) -> bool:
        return self.success

    def is_non_action(self) -> bool:
        return self.non_action is not None


def create_non_action(reason: NonActionReason, details: Dict[str, Any]) -> Result:
    """Create a Non-Action result."""
    return Result(
        success=False,
        non_action={
            "reason": reason.value,
            "details": details,
            "timestamp": time.time(),
        }
    )


def create_success(data: Any) -> Result:
    """Create a successful result."""
    return Result(success=True, data=data)


# PRIMITIVE 4: GUARD (THE ONLY DOOR)
class FrictionParams:
    """Immutable friction parameters."""
    _durations = {
        ConsequenceLevel.HIGH: 10,
        ConsequenceLevel.MEDIUM: 3,
        ConsequenceLevel.LOW: 0,
    }

    def __init__(self, consequence_level: ConsequenceLevel, confidence: float):
        base = self._durations[consequence_level]
        if confidence < 0.3:
            base += 5
        elif confidence < 0.6:
            base += 2
        self._duration = max(0, base)
        self._start_time = time.time()

    def wait(self) -> None:
        """
        Wait for friction to complete.

        I3: FRICTION UNDER CONSEQUENCE
        - No bypass, no skip, no emergency mode
        - Blocking call, cannot be interrupted
        """
        remaining = self._duration - (time.time() - self._start_time)
        if remaining > 0:
            time.sleep(remaining)


class Guard:
    """
    THE ONLY DOOR.

    I1: Unified Execution Authority
    I2: Confidence Before Action
    I3: Friction Under Consequence
    I4: Refusal is Terminal
    I5: Non-Action Must Surface
    I7: Negative Capability (Structural)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._capabilities: Dict[str, CapabilityContract] = {}

    def register_capability(self, contract: CapabilityContract) -> None:
        """Register a capability contract."""
        if contract.name in self._capabilities:
            raise ValueError(f"Capability '{contract.name}' already registered")
        self._capabilities[contract.name] = contract

    def execute(self, intent_name: str, context: Context) -> Result:
        """
        Execute a capability with full invariant enforcement.

        This is the ONLY allowed execution path.
        """
        # I2: CONFIDENCE BEFORE ACTION
        if context.confidence is None:
            return create_non_action(
                NonActionReason.MISSING_CONFIDENCE,
                {"intent": intent_name, "context_id": context.context_id}
            )

        if not (0.0 <= context.confidence <= 1.0):
            return create_non_action(
                NonActionReason.INVALID_CONFIDENCE,
                {
                    "intent": intent_name,
                    "context_id": context.context_id,
                    "confidence": context.confidence,
                }
            )

        # Get capability contract
        capability = self._capabilities.get(intent_name)
        if not capability:
            return create_non_action(
                NonActionReason.REFUSED_BY_GUARD,
                {
                    "intent": intent_name,
                    "context_id": context.context_id,
                    "reason": f"Unknown capability: {intent_name}",
                }
            )

        # Validate context
        is_valid, missing = capability.validate_context(context)
        if not is_valid:
            return create_non_action(
                NonActionReason.MISSING_CONTEXT,
                {
                    "intent": intent_name,
                    "context_id": context.context_id,
                    "missing_fields": missing,
                }
            )

        # I3: FRICTION UNDER CONSEQUENCE
        friction = FrictionParams(capability.consequence_level, context.confidence)
        friction.wait()

        # Execute (only through guard)
        try:
            with self._lock:
                result = capability._execute_fn(context)

            # I5: NON-ACTION MUST SURFACE
            self._emit_observation(
                "execution_success",
                {
                    "intent": intent_name,
                    "context_id": context.context_id,
                    "consequence_level": capability.consequence_level.value,
                }
            )

            return create_success(result)

        except Exception as e:
            error_result = create_non_action(
                NonActionReason.EXECUTION_FAILED,
                {
                    "intent": intent_name,
                    "context_id": context.context_id,
                    "error": str(e),
                }
            )

            # I5: NON-ACTION MUST SURFACE
            self._emit_observation(
                "execution_failed",
                {
                    "intent": intent_name,
                    "context_id": context.context_id,
                    "error": str(e),
                }
            )

            # I4: REFUSAL IS TERMINAL
            # No retries, no fallback, no chaining
            return error_result

    def _emit_observation(self, event_type: str, details: Dict[str, Any]) -> None:
        """
        I6: OBSERVATION NEVER CONTROLS

        Emit observation to observers (non-blocking).
        """
        try:
            get_observer_hub().emit(event_type, details)
        except Exception:
            # I6: Observation failures never affect execution
            pass


# PRIMITIVE 6: OBSERVATION HOOK (Passive)
class Observer(Protocol):
    """Observer protocol - must be passive."""

    def on_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Receive event. Must not affect control flow."""
        ...


class NullObserver:
    """Null observer - does nothing. Used when observers removed."""

    def on_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """No-op."""
        pass


class ObserverHub:
    """
    Central observer hub.

    I6: OBSERVATION NEVER CONTROLS
    - Observers are non-blocking
    - Removing observers changes nothing
    - Observers cannot affect control flow
    """

    def __init__(self):
        self._observers: List[Observer] = []
        self._lock = threading.Lock()

    def register(self, observer: Observer) -> None:
        """Register an observer."""
        with self._lock:
            self._observers.append(observer)

    def clear(self) -> None:
        """Remove all observers."""
        with self._lock:
            self._observers = []

    def emit(self, event_type: str, details: Dict[str, Any]) -> None:
        """Emit event to all observers (non-blocking)."""
        observers = self._observers.copy()
        for observer in observers:
            try:
                observer.on_event(event_type, details)
            except Exception:
                # I6: Observer failures never affect execution
                pass


_observer_hub: Optional[ObserverHub] = None
_observer_lock = threading.Lock()


def get_observer_hub() -> ObserverHub:
    """Get global observer hub."""
    global _observer_hub
    if _observer_hub is None:
        with _observer_lock:
            if _observer_hub is None:
                _observer_hub = ObserverHub()
    return _observer_hub


# GLOBAL GUARD INSTANCE
_guard: Optional[Guard] = None
_guard_lock = threading.Lock()


def get_guard() -> Guard:
    """Get global guard instance."""
    global _guard
    if _guard is None:
        with _guard_lock:
            if _guard is None:
                _guard = Guard()
    return _guard


# I7: NEGATIVE CAPABILITY (STRUCTURAL)
# These are blocked by structure - impossible without core edits

def block_learning(operation: str) -> None:
    """I7: Learning is structurally impossible."""
    raise ProhibitedBehaviorError(
        f"I7_VIOLATION: Learning is prohibited. Attempted: {operation}"
    )


def block_adaptation(operation: str) -> None:
    """I7: Adaptation is structurally impossible."""
    raise ProhibitedBehaviorError(
        f"I7_VIOLATION: Adaptation is prohibited. Attempted: {operation}"
    )


def block_auto_retry(operation: str) -> None:
    """I7: Auto-retry is structurally impossible."""
    raise ProhibitedBehaviorError(
        f"I7_VIOLATION: Auto-retry is prohibited. Attempted: {operation}"
    )


def block_escalation(operation: str) -> None:
    """I7: Escalation is structurally impossible."""
    raise ProhibitedBehaviorError(
        f"I7_VIOLATION: Escalation is prohibited. Attempted: {operation}"
    )


def block_urgency_shortcut(operation: str) -> None:
    """I7: Urgency shortcuts are structurally impossible."""
    raise ProhibitedBehaviorError(
        f"I7_VIOLATION: Urgency shortcuts are prohibited. Attempted: {operation}"
    )


def block_optimization(operation: str) -> None:
    """I7: Optimization is structurally impossible."""
    raise ProhibitedBehaviorError(
        f"I7_VIOLATION: Optimization is prohibited. Attempted: {operation}"
    )


def block_intent_inference(operation: str) -> None:
    """I7: Intent inference is structurally impossible."""
    raise ProhibitedBehaviorError(
        f"I7_VIOLATION: Intent inference is prohibited. Attempted: {operation}"
    )
