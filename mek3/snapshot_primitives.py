"""
MEK-3: Execution Snapshot Primitives

Immutable execution reality snapshot.
State-as-evidence. Anti-rationalization.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
from enum import Enum
import time
import threading
import hashlib
import json
import uuid


class SnapshotHashAlgorithm(Enum):
    """Hash algorithms for snapshot verification."""
    SHA256 = "sha256"
    SHA512 = "sha512"


@dataclass(frozen=True)
class Snapshot:
    """
    Immutable execution snapshot.

    Records everything that made execution permissible.
    TOCTOU immunity: world changes after snapshot = execution refusal.
    """

    snapshot_id: str
    captured_at: float

    # Authority fields
    principal_id: str
    grant_id: str

    # Capability fields
    capability_name: str
    capability_scope_hash: str

    # Context fields (execution-relevant only)
    context_hash: str
    context_fields: Dict[str, Any]

    # Intent fields
    intent_hash: str
    intent_name: str
    intent_value: str

    # Confidence fields
    confidence_range: str
    confidence_value: float

    # Authority fields
    authority_version: int
    grant_expires_at: float
    grant_remaining_uses: Union[int, None]

    def get_hash_representation(self) -> Dict[str, Any]:
        """
        Get hashable representation of snapshot.

        Includes only execution-relevant data.
        """
        return {
            "principal_id": self.principal_id,
            "grant_id": self.grant_id,
            "capability_name": self.capability_name,
            "capability_scope_hash": self.capability_scope_hash,
            "context_fields": self.context_fields,
            "intent_name": self.intent_name,
            "intent_value": self.intent_value,
            "confidence_value": self.confidence_value,
            "authority_version": self.authority_version,
        }


@dataclass(frozen=True)
class SnapshotValidationError:
    """
    Snapshot validation error.

    Returned when snapshot re-validation fails.
    """

    snapshot_id: str
    validated_at: float
    error_type: str
    error_details: Dict[str, Any]


def create_snapshot(
    snapshot_id: str,
    principal_id: str,
    grant_id: str,
    capability_name: str,
    capability_scope_hash: str,
    context_fields: Dict[str, Any],
    intent_name: str,
    intent_value: str,
    confidence: float,
    authority_version: int,
    grant_expires_at: float,
    grant_remaining_uses: Union[int, None] = None,
) -> Snapshot:
    """
    Create an execution snapshot.

    Parameters:
    - snapshot_id: Unique snapshot identifier
    - principal_id: Principal who authorized execution
    - grant_id: Grant authorizing execution
    - capability_name: Name of capability
    - capability_scope_hash: Hash of capability scope
    - context_fields: Actual context field values
    - intent_name: Intent name
    - intent_value: Intent value
    - confidence: Confidence score
    - authority_version: Authority version at snapshot time
    - grant_expires_at: When grant expires
    - grant_remaining_uses: Remaining uses (if applicable)

    Returns:
        Immutable Snapshot object
    """
    captured_at = time.monotonic()

    # Determine confidence range
    if confidence < 0.3:
        confidence_range = "LOW"
    elif confidence < 0.6:
        confidence_range = "MEDIUM"
    elif confidence < 0.8:
        confidence_range = "HIGH"
    else:
        confidence_range = "VERY_HIGH"

    # Hash context
    context_hash = hash_dict(context_fields)

    # Hash intent
    intent_data = f"{intent_name}:{intent_value}"
    intent_hash = hash_bytes(intent_data.encode('utf-8'))

    snapshot = Snapshot(
        snapshot_id=snapshot_id,
        captured_at=captured_at,
        principal_id=principal_id,
        grant_id=grant_id,
        capability_name=capability_name,
        capability_scope_hash=capability_scope_hash,
        context_hash=context_hash,
        context_fields=context_fields,
        intent_hash=intent_hash,
        intent_name=intent_name,
        intent_value=intent_value,
        confidence_range=confidence_range,
        confidence_value=confidence,
        authority_version=authority_version,
        grant_expires_at=grant_expires_at,
        grant_remaining_uses=grant_remaining_uses,
    )

    return snapshot


def hash_dict(data: Dict[str, Any]) -> str:
    """
    Hash a dictionary deterministically.

    Sort keys for consistent hash.
    Use SHA-256 for cryptographic strength.
    """
    sorted_data = json.dumps(data, sort_keys=True, default=str)
    return hash_bytes(sorted_data.encode('utf-8'))


def hash_bytes(data: bytes) -> str:
    """
    Hash bytes using SHA-256.

    Returns hex string.
    """
    return hashlib.sha256(data).hexdigest()


def compare_snapshots(s1: Snapshot, s2: Snapshot) -> bool:
    """
    Compare two snapshots for equality.

    Returns True if all execution-relevant fields match.
    """
    if s1.principal_id != s2.principal_id:
        return False
    if s1.grant_id != s2.grant_id:
        return False
    if s1.capability_name != s2.capability_name:
        return False
    if s1.capability_scope_hash != s2.capability_scope_hash:
        return False
    if s1.context_hash != s2.context_hash:
        return False
    if s1.intent_hash != s2.intent_hash:
        return False
    if s1.authority_version != s2.authority_version:
        return False

    return True


@dataclass(frozen=True)
class SnapshotMismatchError:
    """
    Error raised when snapshot validation detects mismatch.

    This means world changed after snapshot was taken.
    TOCTOU immunity: execution must be refused.
    """

    snapshot_id: str
    field_name: str
    expected_value: Any
    actual_value: Any
    mismatched_at: float

    def __str__(self) -> str:
        return (
            f"SnapshotMismatchError: {self.field_name} mismatch. "
            f"Expected: {self.expected_value}, "
            f"Got: {self.actual_value}"
        )
