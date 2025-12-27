"""
MEK-1: Client Binding & Adapter Prep

AIOS becomes a client governed by MEK.
All execution authority flows through MEK Guard.
"""

from .mek_client import (
    MEKClient,
    MEKRefusalError,
    AIOSContextBridge,
    AIOSIntentBridge,
    get_mek_client,
    execute_via_mek,
)

from .capability_wrappers import (
    AIOSCapabilityWrapper,
    wrap_aios_capability,
    wrap_filesystem_capability,
    wrap_process_capability,
    wrap_vision_capability,
    wrap_stt_capability,
    wrap_code_capability,
)

from .authority_sealing import (
    LegacyExecutionBlockedError,
    block_legacy_execution,
    seal_aios_authority,
    assert_mek_refusal_halts_aios,
    verify_no_legacy_paths,
    enforce_authority_sealing,
)

from .observer_wiring import (
    AIOSObserverBridge,
    MEKWrappedObserver,
    LoggingObserver,
)

from .adapter_interfaces import (
    AdapterProtocol,
    HTTPAdapterContract,
    CLIAdapterContract,
    UIAdapterContract,
    AdapterConstraintValidator,
    assert_adapter_is_contract_only,
    assert_adapter_cannot_execute,
    assert_adapter_cannot_bypass_guard,
)

__version__ = "0.1.0"
__all__ = [
    # Client binding
    "MEKClient",
    "MEKRefusalError",
    "AIOSContextBridge",
    "AIOSIntentBridge",
    "get_mek_client",
    "execute_via_mek",
    # Capability wrapping
    "AIOSCapabilityWrapper",
    "wrap_aios_capability",
    "wrap_filesystem_capability",
    "wrap_process_capability",
    "wrap_vision_capability",
    "wrap_stt_capability",
    "wrap_code_capability",
    # Authority sealing
    "LegacyExecutionBlockedError",
    "block_legacy_execution",
    "seal_aios_authority",
    "assert_mek_refusal_halts_aios",
    "verify_no_legacy_paths",
    "enforce_authority_sealing",
    # Observer wiring
    "AIOSObserverBridge",
    "MEKWrappedObserver",
    "LoggingObserver",
    # Adapter interfaces
    "AdapterProtocol",
    "HTTPAdapterContract",
    "CLIAdapterContract",
    "UIAdapterContract",
    "AdapterConstraintValidator",
    "assert_adapter_is_contract_only",
    "assert_adapter_cannot_execute",
    "assert_adapter_cannot_bypass_guard",
]
