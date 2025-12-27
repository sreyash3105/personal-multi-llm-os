"""
MEK-6: Hash Chain

Deterministic hashing of bundle elements.
Any mutation breaks verification.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class HashChain:
    """
    Deterministic hash chain for bundle elements.

    - Every element contributes to hash chain
    - Order is fixed and deterministic
    - Any mutation breaks verification
    - Hash algorithm is fixed and explicit (SHA-256)
    """

    def __init__(self, algorithm: str = "sha256"):
        """
        Initialize hash chain.

        Args:
            algorithm: Hash algorithm (default: sha256)
        """
        self.algorithm = algorithm
        self.current_hash = ""
        self.elements: list[tuple[str, str]] = []

    def add_element(self, key: str, value: Any) -> None:
        """
        Add element to hash chain.

        Args:
            key: Element key (deterministic ordering)
            value: Element value (any JSON-serializable)
        """
        # Serialize value to JSON (deterministic)
        if hasattr(value, "__dict__"):
            serialized = json.dumps(value.__dict__, sort_keys=True, separators=(",", ":"))
        else:
            serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))

        # Hash element
        hash_obj = hashlib.new(self.algorithm)
        hash_obj.update(f"{key}:{serialized}".encode("utf-8"))
        element_hash = hash_obj.hexdigest()

        # Add to chain
        self.elements.append((key, element_hash))

        # Update current hash
        self.current_hash = self._chain_hash(element_hash)

    def _chain_hash(self, element_hash: str) -> str:
        """
        Chain hash with previous hash.

        Args:
            element_hash: Hash of current element

        Returns:
            New chained hash
        """
        if not self.current_hash:
            return element_hash

        # Hash: previous_hash + element_hash
        hash_obj = hashlib.new(self.algorithm)
        hash_obj.update(f"{self.current_hash}:{element_hash}".encode("utf-8"))
        return hash_obj.hexdigest()

    def get_root(self) -> str:
        """
        Get root hash of chain.

        Returns:
            Root hash of entire chain
        """
        return self.current_hash

    def get_elements(self) -> list[tuple[str, str]]:
        """
        Get all elements in chain.

        Returns:
            List of (key, hash) tuples
        """
        return list(self.elements)

    def verify(self, root_hash: str) -> bool:
        """
        Verify hash chain matches root.

        Args:
            root_hash: Expected root hash

        Returns:
            True if verification succeeds
        """
        return self.current_hash == root_hash

    def get_hash(self, key: str, value: Any) -> str:
        """
        Get hash of a single element.

        Args:
            key: Element key
            value: Element value

        Returns:
            Hash of element
        """
        if hasattr(value, "__dict__"):
            serialized = json.dumps(value.__dict__, sort_keys=True, separators=(",", ":"))
        else:
            serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))

        hash_obj = hashlib.new(self.algorithm)
        hash_obj.update(f"{key}:{serialized}".encode("utf-8"))
        return hash_obj.hexdigest()


def hash_value(value: Any, algorithm: str = "sha256") -> str:
    """
    Hash a value.

    Args:
        value: Value to hash
        algorithm: Hash algorithm

    Returns:
        Hash string
    """
    if hasattr(value, "__dict__"):
        serialized = json.dumps(value.__dict__, sort_keys=True, separators=(",", ":"))
    else:
        serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))

    hash_obj = hashlib.new(algorithm)
    hash_obj.update(serialized.encode("utf-8"))
    return hash_obj.hexdigest()


def verify_hash(value: Any, expected_hash: str, algorithm: str = "sha256") -> bool:
    """
    Verify a value against expected hash.

    Args:
        value: Value to verify
        expected_hash: Expected hash
        algorithm: Hash algorithm

    Returns:
        True if verification succeeds
    """
    actual_hash = hash_value(value, algorithm)
    return actual_hash == expected_hash
