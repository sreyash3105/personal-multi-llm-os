"""
MEK-0: Minimal Execution Kernel

Constitution-as-Code.
"""

from .kernel import (
    # Primitives
    Context,
    Intent,
    CapabilityContract,
    Guard,
    Result,
    NonActionReason,

    # Enums
    ConsequenceLevel,

    # Errors
    InvariantViolationError,
    ProhibitedBehaviorError,

    # Factories
    create_non_action,
    create_success,

    # Singleton accessors
    get_guard,
    get_observer_hub,

    # Observer protocol
    Observer,
    NullObserver,
    ObserverHub,

    # I7: Negative capability blocks
    block_learning,
    block_adaptation,
    block_auto_retry,
    block_escalation,
    block_urgency_shortcut,
    block_optimization,
    block_intent_inference,
)

__version__ = "0.1.0"
__all__ = [
    # Primitives
    "Context",
    "Intent",
    "CapabilityContract",
    "Guard",
    "Result",
    "NonActionReason",
    # Enums
    "ConsequenceLevel",
    # Errors
    "InvariantViolationError",
    "ProhibitedBehaviorError",
    # Factories
    "create_non_action",
    "create_success",
    # Singleton accessors
    "get_guard",
    "get_observer_hub",
    # Observer protocol
    "Observer",
    "NullObserver",
    "ObserverHub",
    # I7: Negative capability blocks
    "block_learning",
    "block_adaptation",
    "block_auto_retry",
    "block_escalation",
    "block_urgency_shortcut",
    "block_optimization",
    "block_intent_inference",
]
