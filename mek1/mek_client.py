"""
MEK-1: Client Binding Layer

AIOS becomes a client governed by MEK.
All execution authority flows through MEK Guard.
"""

from __future__ import annotations

from typing import Any
import threading


class AIOSContextBridge:
    """
    Bridge between AIOS Context and MEK Context.

    Maps AIOS context to MEK context explicitly.
    No inference, no defaults.
    """

    @staticmethod
    def to_mek_context(
        aios_context: Any,
        confidence: float,
        intent_name: str,
    ) -> Any:
        """
        Convert AIOS context to MEK context.

        Rules:
        - Explicit mapping only
        - No inference of missing fields
        - Missing confidence -> refusal (raises ValueError)
        """
        if confidence is None:
            raise ValueError(
                "AIOS Context: confidence is required. "
                "Cannot invoke MEK without explicit confidence."
            )

        if not (0.0 <= confidence <= 1.0):
            raise ValueError(
                f"AIOS Context: confidence must be 0.0-1.0, got {confidence}"
            )

        # Import MEK Context at runtime
        from mek0.kernel import Context

        # Extract fields from AIOS context
        fields = {}
        if hasattr(aios_context, 'profile_id'):
            fields['profile_id'] = aios_context.profile_id
        if hasattr(aios_context, 'session_id'):
            fields['session_id'] = aios_context.session_id
        if hasattr(aios_context, 'metadata'):
            if isinstance(aios_context.metadata, dict):
                fields.update(aios_context.metadata)

        # Create immutable MEK context
        return Context(
            context_id=str(hasattr(aios_context, 'context_id') and aios_context.context_id or "unknown"),
            confidence=confidence,
            intent=intent_name,
            fields=fields,
        )


class AIOSIntentBridge:
    """
    Bridge between AIOS Intent and MEK Intent.

    Maps AIOS intent to MEK intent explicitly.
    No inference, no ranking, no fallback.
    """

    @staticmethod
    def to_mek_intent(aios_intent_name: str) -> Any:
        """
        Convert AIOS intent to MEK intent.

        Rules:
        - Explicit mapping only
        - No inference of "similar" intents
        - Unknown intent -> refusal (raises ValueError)
        """
        if not aios_intent_name:
            raise ValueError(
                "AIOS Intent: intent name is required. "
                "Cannot invoke MEK without explicit intent."
            )

        # Import MEK Intent at runtime
        from mek0.kernel import Intent

        return Intent(
            name=aios_intent_name,
            description=f"AIOS intent: {aios_intent_name}",
        )


class MEKClient:
    """
    MEK Client - AIOS binding to MEK kernel.

    AIOS MUST NOT call MEK internals directly.
    AIOS MUST NOT execute capabilities directly.
    All execution MUST pass through this client.
    """

    def __init__(self):
        from mek0.kernel import get_guard
        self._guard = get_guard()

    def execute_intent(
        self,
        intent_name: str,
        aios_context: Any,
        confidence: float,
    ) -> Any:
        """
        Execute an intent through MEK Guard.

        This is the ONLY allowed execution path for AIOS.

        Flow:
        1. Validate AIOS intent
        2. Validate confidence
        3. Convert AIOS context to MEK context
        4. Invoke MEK Guard
        5. Return result (success or non-action)

        MEK-1: Authority Sealing
        - AIOS cannot execute without MEK
        - MEK refusal halts AIOS unconditionally
        - No alternate path exists
        """
        # Step 1: Convert intent (explicit)
        mek_intent = AIOSIntentBridge.to_mek_intent(intent_name)

        # Step 2: Convert context (explicit)
        mek_context = AIOSContextBridge.to_mek_context(
            aios_context=aios_context,
            confidence=confidence,
            intent_name=intent_name,
        )

        # Step 3: Execute via MEK Guard (ONLY PATH)
        result = self._guard.execute(intent_name, mek_context)

        # Step 4: MEK refusal halts AIOS (no bypass)
        from mek0.kernel import Result
        if isinstance(result, Result):
            if not result.is_success():
                # MEK refused - AIOS must stop
                # No retry, no fallback, no alternate path
                raise MEKRefusalError(
                    f"MEK refused intent '{intent_name}'. "
                    f"Reason: {result.non_action.get('reason', 'unknown')}. "
                    "AIOS execution halted unconditionally."
                )

        return result

    def register_aios_capability(self, capability_contract: Any) -> None:
        """
        Register an AIOS capability with MEK.

        The capability must be wrapped as MEK CapabilityContract.
        """
        self._guard.register_capability(capability_contract)


class MEKRefusalError(RuntimeError):
    """
    Raised when MEK refuses execution.

    This is TERMINAL for AIOS.
    AIOS must stop - no retry, no fallback, no alternate path.
    """

    pass


# Singleton client instance
_client = None
_client_lock = threading.Lock()


def get_mek_client():
    """
    Get global MEK client instance.

    AIOS MUST use this client for all execution.
    AIOS MUST NOT call MEK internals directly.
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = MEKClient()
    return _client


def execute_via_mek(
    intent_name: str,
    aios_context: Any,
    confidence: float,
) -> Any:
    """
    Convenience function to execute via MEK client.

    This is the ONLY allowed execution path for AIOS code.

    Raises MEKRefusalError if MEK refuses.
    """
    client = get_mek_client()
    return client.execute_intent(intent_name, aios_context, confidence)
