"""
MEK-X SANDBOX ADAPTER

Enforces isolation between MEK-X and MEK.

MEK-X cannot access MEK.
MEK cannot access MEK-X internals.

Build Prompt: MEK-X — SANDBOXED INTELLIGENCE ZONE
"""

from __future__ import annotations

from typing import Dict, Any, Optional
import sys


class SandboxError(RuntimeError):
    """Raised when MEK-X tries to access MEK."""
    pass


class SandboxAdapter:
    """
    Enforces MEK-X isolation.

    MEK-X imports are restricted.
    MEK imports are FORBIDDEN.
    """

    _FORBIDDEN_IMPORTS = {
        "mek0",
        "mek1",
        "mek2",
        "mek3",
        "mek4",
        "mek5",
        "mek6",
        "backend.core.capability",
        "backend.core.capabilities",
        "backend.core.guard",
        "backend.core.local_runner",
        "backend.core.execution_guard",
        "backend.core.snapshot_guard",
        "backend.core.composition_guard",
        "backend.core.failure_guard",
    }

    @staticmethod
    def check_import(module_name: str) -> None:
        """
        Check if import is allowed.

        Raises SandboxError if forbidden.
        """
        for forbidden in SandboxAdapter._FORBIDDEN_IMPORTS:
            if module_name.startswith(forbidden):
                raise SandboxError(
                    f"FORBIDDEN: MEK-X cannot import '{module_name}'. "
                    "MEK-X is isolated from MEK."
                )


_import_hook_installed = False


def install_import_hook():
    """Install import hook to enforce isolation."""
    global _import_hook_installed

    if _import_hook_installed:
        return

    class MEKXSandboxFinder:
        def find_module(self, fullname, path=None):
            SandboxAdapter.check_import(fullname)
            return None

        def find_spec(self, fullname, path=None, target=None):
            SandboxAdapter.check_import(fullname)
            return None

    sys.meta_path.insert(0, MEKXSandboxFinder())
    _import_hook_installed = True
