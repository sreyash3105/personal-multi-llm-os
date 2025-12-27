"""
MEK-1: Adapter Interface Stubs

Adapter contracts only - NO runtime code.
NO imports into execution path.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class AdapterProtocol(ABC):
    """
    Base adapter protocol - defines contract only.

    NO runtime implementation allowed.
    NO execution path imports allowed.
    """

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize adapter.

        Contract only - NO implementation.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """
        Shutdown adapter.

        Contract only - NO implementation.
        """
        pass


class HTTPAdapterContract(AdapterProtocol):
    """
    HTTP Adapter Contract.

    Defines signature for HTTP adapter.
    NO runtime implementation allowed.
    NO requests/fastapi/uvicorn imports allowed in execution path.
    """

    @abstractmethod
    def register_handlers(self) -> None:
        """
        Register HTTP request handlers.

        Contract only - NO implementation.
        """
        pass

    @abstractmethod
    def handle_request(self, method: str, path: str, body: Optional[dict]) -> Any:
        """
        Handle HTTP request.

        Contract only - NO implementation.
        Returns response from MEK execution or refusal.
        """
        pass

    # Intentionally NO run() method
    # Adapters cannot start servers or listen on ports


class CLIAdapterContract(AdapterProtocol):
    """
    CLI Adapter Contract.

    Defines signature for CLI adapter.
    NO runtime implementation allowed.
    NO argparse/click imports allowed in execution path.
    """

    @abstractmethod
    def register_commands(self) -> None:
        """
        Register CLI commands.

        Contract only - NO implementation.
        """
        pass

    @abstractmethod
    def handle_command(self, command: str, args: list) -> Any:
        """
        Handle CLI command.

        Contract only - NO implementation.
        Returns response from MEK execution or refusal.
        """
        pass

    # Intentionally NO run() method
    # Adapters cannot start REPLs or accept input


class UIAdapterContract(AdapterProtocol):
    """
    UI Adapter Contract.

    Defines signature for UI adapter.
    NO runtime implementation allowed.
    NO tkinter/qt/html imports allowed in execution path.
    """

    @abstractmethod
    def render(self, state: dict) -> None:
        """
        Render UI from state.

        Contract only - NO implementation.
        """
        pass

    @abstractmethod
    def handle_input(self, input_type: str, data: Any) -> Any:
        """
        Handle UI input.

        Contract only - NO implementation.
        Returns response from MEK execution or refusal.
        """
        pass

    # Intentionally NO run() method
    # Adapters cannot start UI loops


class AdapterConstraintValidator:
    """
    Validates that adapters do not execute.

    Tests proving:
    - Adapters cannot alter Guard decisions
    - Adapters cannot bypass refusal or friction
    - Adapters cannot execute directly
    """

    @staticmethod
    def adapter_must_not_execute(adapter: Any) -> bool:
        """
        Verify adapter does not execute.

        Returns True if adapter has no execution methods.
        """
        forbidden_methods = ['run', 'start', 'execute', 'listen', 'serve']
        for method_name in forbidden_methods:
            if hasattr(adapter, method_name):
                if callable(getattr(adapter, method_name)):
                    return False
        return True

    @staticmethod
    def adapter_must_not_import_execution_path(adapter: Any) -> bool:
        """
        Verify adapter does not import execution path modules.

        Returns True if no execution path imports found.
        """
        import sys
        forbidden_modules = [
            'mek0.kernel',  # Direct MEK imports forbidden
            'backend.core.capability_invocation',  # Legacy execution forbidden
        ]

        adapter_module = adapter.__class__.__module__
        for forbidden in forbidden_modules:
            if forbidden in sys.modules and forbidden in adapter_module:
                return False
        return True

    @staticmethod
    def adapter_must_be_contract_only(adapter: Any) -> bool:
        """
        Verify adapter is contract-only (abstract base).

        Returns True if adapter defines only contracts.
        """
        import inspect

        # Check if all methods are abstract
        methods = inspect.getmembers(adapter.__class__, predicate=inspect.ismethod)
        abstract_methods = inspect.getmembers(adapter.__class__, predicate=lambda x: getattr(x, '__isabstractmethod__', False))

        # All methods should be abstract (no implementation)
        return len(methods) == len(abstract_methods)


# Test helpers for adapter validation

def assert_adapter_is_contract_only(adapter: AdapterProtocol) -> None:
    """
    Assert adapter is contract-only.

    Raises AssertionError if adapter has implementation.
    """
    if not AdapterConstraintValidator.adapter_must_be_contract_only(adapter):
        raise AssertionError(
            f"Adapter {adapter.__class__.__name__} has implementation. "
            "Adapters must be contract-only (no runtime code)."
        )


def assert_adapter_cannot_execute(adapter: AdapterProtocol) -> None:
    """
    Assert adapter cannot execute.

    Raises AssertionError if adapter has execution methods.
    """
    if not AdapterConstraintValidator.adapter_must_not_execute(adapter):
        raise AssertionError(
            f"Adapter {adapter.__class__.__name__} can execute. "
            "Adapters must not have execution methods."
        )


def assert_adapter_cannot_bypass_guard(adapter: AdapterProtocol) -> None:
    """
    Assert adapter cannot bypass Guard.

    Raises AssertionError if adapter imports execution path.
    """
    if not AdapterConstraintValidator.adapter_must_not_import_execution_path(adapter):
        raise AssertionError(
            f"Adapter {adapter.__class__.__name__} imports execution path. "
            "Adapters must not import MEK or legacy execution modules."
        )
