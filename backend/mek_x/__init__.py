"""
MEK-X: SANDBOXED INTELLIGENCE ZONE

Zero Authority. Total Containment. Maximum Power.

MEK-X may think.
MEK-X may suggest.
MEK-X may simulate.
MEK-X may be wrong.

MEK-X may never act.

Build Prompt: MEK-X — SANDBOXED INTELLIGENCE ZONE
"""

from backend.mek_x.proposal import (
    Proposal,
    ConfidenceRange,
    create_proposal,
)

from backend.mek_x.intelligence import (
    IntelligenceEngine,
    MemoryEntry,
    Hypothesis,
    get_intelligence_engine,
)

from backend.mek_x.sandbox import (
    SandboxError,
    SandboxAdapter,
    install_import_hook,
)


__all__ = [
    "Proposal",
    "ConfidenceRange",
    "create_proposal",
    "IntelligenceEngine",
    "MemoryEntry",
    "Hypothesis",
    "get_intelligence_engine",
    "SandboxError",
    "SandboxAdapter",
    "install_import_hook",
]
