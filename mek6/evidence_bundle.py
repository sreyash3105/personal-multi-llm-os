"""
MEK-6: Evidence Bundle Primitives

Verifiable proof bundles.
Evidence is proof, not narrative.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ContextSnapshot:
    """
    Immutable snapshot of execution context.
    """

    context_id: str
    principal_id: str
    intent: str
    confidence: float
    fields: Dict[str, Any]
    timestamp: int


@dataclass(frozen=True)
class IntentSnapshot:
    """
    Immutable snapshot of declared intent.
    """

    intent_name: str
    capability_name: str
    declared_at: int


@dataclass(frozen=True)
class PrincipalSnapshot:
    """
    Immutable snapshot of principal.
    """

    principal_id: str
    verified_at: int


@dataclass(frozen=True)
class GrantSnapshot:
    """
    Immutable snapshot of grant.
    """

    grant_id: str
    principal_id: str
    capability_name: str
    scope: Dict[str, Any]
    issued_at: int
    expires_at: int
    remaining_uses: int


@dataclass(frozen=True)
class ExecutionSnapshot:
    """
    Immutable snapshot of single execution.
    """

    step_id: Optional[str]
    capability_name: str
    context_hash: str
    snapshot_id: str
    executed_at: int
    is_success: bool
    result_data: Optional[Dict[str, Any]] = None
    non_action: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class EvidenceBundle:
    """
    Immutable evidence bundle.

    Captures exactly what happened.
    Exactly one of failure_composition or results is present.

    Fields:
        bundle_id: Unique identifier
        created_at: Monotonic timestamp
        context_snapshot: Context snapshot
        intent_snapshot: Intent snapshot
        principal_snapshot: Principal snapshot
        grant_snapshot: Grant snapshot (if applicable)
        execution_snapshots: List of execution snapshots
        failure_composition: Failure composition (if execution failed)
        results: Execution results (if execution succeeded)
        authority_version: MEK authority version
        hash_chain_root: Root of hash chain

    Rules:
        - Bundle is created after execution halts
        - Exactly one of failure_composition or results is present
        - Bundle is immutable after creation
        - No derived fields
    """

    bundle_id: str
    created_at: int
    context_snapshot: ContextSnapshot
    intent_snapshot: IntentSnapshot
    principal_snapshot: PrincipalSnapshot
    grant_snapshot: Optional[GrantSnapshot]
    execution_snapshots: List[ExecutionSnapshot]
    authority_version: str
    hash_chain_root: str
    failure_composition: Optional[Dict[str, Any]] = None
    results: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        """
        Validate evidence bundle after creation.

        Raises ValueError if invalid.
        """
        if not self.bundle_id:
            raise ValueError("bundle_id is required")

        if not self.created_at:
            raise ValueError("created_at is required")

        if not self.context_snapshot:
            raise ValueError("context_snapshot is required")

        if not self.intent_snapshot:
            raise ValueError("intent_snapshot is required")

        if not self.principal_snapshot:
            raise ValueError("principal_snapshot is required")

        if not self.authority_version:
            raise ValueError("authority_version is required")

        if not self.hash_chain_root:
            raise ValueError("hash_chain_root is required")

        # Exactly one of failure_composition or results must be present
        has_failure = self.failure_composition is not None
        has_results = self.results is not None

        if has_failure and has_results:
            raise ValueError(
                "Exactly one of failure_composition or results must be present"
            )

        if not has_failure and not has_results:
            raise ValueError(
                "Exactly one of failure_composition or results must be present"
            )


@dataclass(frozen=True)
class VerificationResult:
    """
    Result of bundle verification.

    Verification performs only structural + hash checks.
    Never evaluates "correctness".
    """

    is_valid: bool
    bundle_id: str
    hash_valid: bool
    structure_valid: bool
    integrity_valid: bool
    errors: List[str] = field(default_factory=list)


def create_evidence_bundle(
    context_snapshot: ContextSnapshot,
    intent_snapshot: IntentSnapshot,
    principal_snapshot: PrincipalSnapshot,
    grant_snapshot: Optional[GrantSnapshot],
    execution_snapshots: List[ExecutionSnapshot],
    failure_composition: Optional[Dict[str, Any]] = None,
    results: Optional[List[Dict[str, Any]]] = None,
    authority_version: str = "1.0",
) -> EvidenceBundle:
    """
    Create an evidence bundle.

    Validates input before creation.
    """
    import time
    from hash_chain import HashChain

    bundle_id = str(uuid.uuid4())
    created_at = int(time.time() * 1000)

    # Create hash chain
    hash_chain = HashChain()
    hash_chain.add_element("context", context_snapshot)
    hash_chain.add_element("intent", intent_snapshot)
    hash_chain.add_element("principal", principal_snapshot)

    if grant_snapshot:
        hash_chain.add_element("grant", grant_snapshot)

    for i, exec_snap in enumerate(execution_snapshots):
        hash_chain.add_element(f"execution_{i}", exec_snap)

    if failure_composition:
        hash_chain.add_element("failure", failure_composition)

    if results:
        hash_chain.add_element("results", results)

    hash_chain.add_element("authority_version", authority_version)

    return EvidenceBundle(
        bundle_id=bundle_id,
        created_at=created_at,
        context_snapshot=context_snapshot,
        intent_snapshot=intent_snapshot,
        principal_snapshot=principal_snapshot,
        grant_snapshot=grant_snapshot,
        execution_snapshots=execution_snapshots,
        failure_composition=failure_composition,
        results=results,
        authority_version=authority_version,
        hash_chain_root=hash_chain.get_root(),
    )


def create_context_snapshot(
    context_id: str,
    principal_id: str,
    intent: str,
    confidence: float,
    fields: Dict[str, Any],
) -> ContextSnapshot:
    """
    Create a context snapshot.
    """
    import time

    return ContextSnapshot(
        context_id=context_id,
        principal_id=principal_id,
        intent=intent,
        confidence=confidence,
        fields=dict(fields),
        timestamp=int(time.time() * 1000),
    )


def create_intent_snapshot(
    intent_name: str,
    capability_name: str,
) -> IntentSnapshot:
    """
    Create an intent snapshot.
    """
    import time

    return IntentSnapshot(
        intent_name=intent_name,
        capability_name=capability_name,
        declared_at=int(time.time() * 1000),
    )


def create_principal_snapshot(
    principal_id: str,
) -> PrincipalSnapshot:
    """
    Create a principal snapshot.
    """
    import time

    return PrincipalSnapshot(
        principal_id=principal_id,
        verified_at=int(time.time() * 1000),
    )


def create_grant_snapshot(
    grant_id: str,
    principal_id: str,
    capability_name: str,
    scope: Dict[str, Any],
    issued_at: int,
    expires_at: int,
    remaining_uses: int,
) -> GrantSnapshot:
    """
    Create a grant snapshot.
    """
    return GrantSnapshot(
        grant_id=grant_id,
        principal_id=principal_id,
        capability_name=capability_name,
        scope=dict(scope),
        issued_at=issued_at,
        expires_at=expires_at,
        remaining_uses=remaining_uses,
    )


def create_execution_snapshot(
    step_id: Optional[str],
    capability_name: str,
    context_hash: str,
    snapshot_id: str,
    is_success: bool,
    result_data: Optional[Dict[str, Any]] = None,
    non_action: Optional[Dict[str, Any]] = None,
) -> ExecutionSnapshot:
    """
    Create an execution snapshot.
    """
    import time

    return ExecutionSnapshot(
        step_id=step_id,
        capability_name=capability_name,
        context_hash=context_hash,
        snapshot_id=snapshot_id,
        executed_at=int(time.time() * 1000),
        is_success=is_success,
        result_data=result_data,
        non_action=non_action,
    )
