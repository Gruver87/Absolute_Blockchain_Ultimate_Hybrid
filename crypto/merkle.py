# crypto/merkle.py
"""
Merkle Tree implementation for transaction proofs
"""

from typing import List, Any

from crypto import native


def hash_data(data: Any) -> str:
    """Hash any data with SHA256"""
    return native.hash_data(data)


def merkle_root(items: List[Any]) -> str:
    """
    Compute Merkle root from list of items
    """
    return native.merkle_root(items)


def generate_proof(items: List[Any], target_index: int) -> List[str]:
    """
    Generate Merkle proof for item at target_index
    Returns list of sibling hashes for verification
    """
    return native.generate_proof(items, target_index)


def verify_proof(item: Any, proof: List[str], expected_root: str, target_index: int) -> bool:
    """
    Verify that item is included in Merkle tree with given root
    """
    return native.verify_proof(item, proof, expected_root, target_index)


def merkle_root_from_proof(item: Any, proof: List[str], target_index: int) -> str:
    """
    Reconstruct Merkle root from item and proof
    """
    return native.merkle_root_from_proof(item, proof, target_index)
