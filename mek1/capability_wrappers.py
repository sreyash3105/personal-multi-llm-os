"""
MEK-1: Capability Wrapping

Wrap existing AIOS capabilities as MEK CapabilityContracts.
No new capabilities. No behavior changes.
"""

from __future__ import annotations

from typing import Any, List
from dataclasses import dataclass


@dataclass(frozen=True)
class AIOSCapabilityWrapper:
    """
    Wrapper that converts AIOS capability to MEK CapabilityContract.

    Rules:
    - No new capabilities
    - No behavior changes
    - Removal must not break MEK
    - Direct invocation forbidden
    """

    name: str
    original_capability: Any
    consequence_level_str: str
    required_context_fields: List[str]

    def to_mek_contract(self) -> Any:
        """
        Convert to MEK CapabilityContract.

        Execution is private - cannot be called directly.
        """
        from mek0.kernel import CapabilityContract, ConsequenceLevel

        # Map consequence level string to enum
        consequence_map = {
            "LOW": ConsequenceLevel.LOW,
            "MEDIUM": ConsequenceLevel.MEDIUM,
            "HIGH": ConsequenceLevel.HIGH,
        }
        consequence = consequence_map.get(self.consequence_level_str.upper())
        if consequence is None:
            raise ValueError(
                f"Invalid consequence level: {self.consequence_level_str}. "
                f"Must be LOW, MEDIUM, or HIGH."
            )

        # Create wrapper function
        def _mek_execute_fn(mek_context: Any) -> Any:
            """
            MEK-Contracted execution wrapper.

            Only invoked via MEK Guard.
            Direct calls are structurally forbidden.
            """
            # Convert MEK context back to AIOS context
            aios_context = self._mek_to_aios_context(mek_context)

            # Invoke original capability
            return self.original_capability(aios_context)

        return CapabilityContract(
            name=self.name,
            consequence_level=consequence,
            required_context_fields=self.required_context_fields,
            _execute_fn=_mek_execute_fn,
        )

    def _mek_to_aios_context(self, mek_context: Any) -> Any:
        """
        Convert MEK context back to AIOS context format.

        Explicit mapping only. No inference.
        """
        # Simple pass-through for AIOS context
        # AIOS modules expect dict-like context
        return mek_context.fields


def wrap_aios_capability(
    name: str,
    original_capability: Any,
    consequence_level: str,
    required_context_fields: List[str],
) -> AIOSCapabilityWrapper:
    """
    Wrap an AIOS capability for MEK.

    Parameters:
    - name: Capability name
    - original_capability: Original AIOS capability function
    - consequence_level: "LOW" | "MEDIUM" | "HIGH"
    - required_context_fields: List of required context field names

    Returns:
        AIOSCapabilityWrapper that can be converted to MEK contract
    """
    return AIOSCapabilityWrapper(
        name=name,
        original_capability=original_capability,
        consequence_level_str=consequence_level,
        required_context_fields=required_context_fields,
    )


# Pre-defined wrappers for common AIOS capabilities
# These are READ-ONLY - no execution allowed without MEK Guard


def wrap_filesystem_capability(
    name: str,
    execute_fn: Any,
) -> AIOSCapabilityWrapper:
    """
    Wrap filesystem capability with HIGH consequence.
    """
    return wrap_aios_capability(
        name=name,
        original_capability=execute_fn,
        consequence_level="HIGH",
        required_context_fields=["path", "operation"],
    )


def wrap_process_capability(
    name: str,
    execute_fn: Any,
) -> AIOSCapabilityWrapper:
    """
    Wrap process capability with HIGH consequence.
    """
    return wrap_aios_capability(
        name=name,
        original_capability=execute_fn,
        consequence_level="HIGH",
        required_context_fields=["command", "args"],
    )


def wrap_vision_capability(
    name: str,
    execute_fn: Any,
) -> AIOSCapabilityWrapper:
    """
    Wrap vision capability with MEDIUM consequence.
    """
    return wrap_aios_capability(
        name=name,
        original_capability=execute_fn,
        consequence_level="MEDIUM",
        required_context_fields=["image_data"],
    )


def wrap_stt_capability(
    name: str,
    execute_fn: Any,
) -> AIOSCapabilityWrapper:
    """
    Wrap STT capability with LOW consequence.
    """
    return wrap_aios_capability(
        name=name,
        original_capability=execute_fn,
        consequence_level="LOW",
        required_context_fields=["audio_data"],
    )


def wrap_code_capability(
    name: str,
    execute_fn: Any,
) -> AIOSCapabilityWrapper:
    """
    Wrap code capability with MEDIUM consequence.
    """
    return wrap_aios_capability(
        name=name,
        original_capability=execute_fn,
        consequence_level="MEDIUM",
        required_context_fields=["prompt"],
    )
