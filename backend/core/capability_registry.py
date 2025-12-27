"""
Capability registry - static, read-only.

All capabilities are defined here.
Runtime registration is NOT allowed.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from backend.core.capability import (
    CapabilityDescriptor,
    ConsequenceLevel,
    RefusalReason,
)


_registry: Dict[str, CapabilityDescriptor] = {}
_registry_locked = False


def register_capability(capability: CapabilityDescriptor) -> None:
    """
    Register a capability at startup only.
    Raises RuntimeError if called after registry is locked.
    """
    global _registry_locked
    if _registry_locked:
        raise RuntimeError(
            "Capability registry is locked. No runtime registration allowed."
        )

    if capability.name in _registry:
        raise ValueError(f"Capability '{capability.name}' already registered")

    _registry[capability.name] = capability


def lock_registry() -> None:
    """
    Lock the registry to prevent runtime modifications.
    """
    global _registry_locked
    _registry_locked = True


def get_capability(name: str) -> Optional[CapabilityDescriptor]:
    """
    Get a capability by name.
    Returns None if not found.
    """
    return _registry.get(name)


def list_capabilities() -> List[CapabilityDescriptor]:
    """
    List all registered capabilities.
    """
    return list(_registry.values())


def get_capabilities_by_scope(scope: str) -> List[CapabilityDescriptor]:
    """
    Get all capabilities for a given scope.
    """
    return [cap for cap in _registry.values() if cap.scope == scope]


def get_high_consequence_capabilities() -> List[CapabilityDescriptor]:
    """
    Get all HIGH consequence capabilities.
    """
    return [
        cap for cap in _registry.values()
        if cap.consequence_level == ConsequenceLevel.HIGH
    ]


def is_registered(name: str) -> bool:
    """
    Check if a capability is registered.
    """
    return name in _registry


def initialize_registry(capabilities: List[CapabilityDescriptor]) -> None:
    """
    Initialize the registry with a list of capabilities.
    Should be called exactly once at startup.
    """
    global _registry
    if _registry:
        raise RuntimeError("Registry already initialized")
    for cap in capabilities:
        register_capability(cap)
    lock_registry()
