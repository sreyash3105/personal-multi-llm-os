"""
Capability package - all kernel capabilities.
"""

from __future__ import annotations

from backend.core.capabilities.filesystem import create_filesystem_capability
from backend.core.capabilities.process import create_process_capability
from backend.core.capabilities.screen import create_screen_capability

from backend.core.capability_registry import register_capability, lock_registry, initialize_registry


def load_capabilities() -> None:
    """
    Register all capabilities at startup.
    Must be called exactly once during initialization.
    """
    caps = [
        create_filesystem_capability(),
        create_process_capability(),
        create_screen_capability(),
    ]
    initialize_registry(caps)
