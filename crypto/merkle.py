# crypto/merkle.py
"""
Merkle Tree implementation for transaction proofs
"""

import hashlib
from typing import List, Any


def hash_data(data: Any) -> str:
    """Hash any data with SHA256"""
    return hashlib.sha256(str(data).encode()).hexdigest()


def merkle_root(items: List[Any]) -> str:
    """
    Compute Merkle root from list of items
    """
    if not items:
        return hash_data("empty")

    # Hash all items
    layer = [hash_data(item) for item in items]

    # Build tree
    while len(layer) > 1:
        # Duplicate last if odd
        if len(layer) % 2 == 1:
            layer.append(layer[-1])

        new_layer = []
        for i in range(0, len(layer), 2):
            combined = layer[i] + layer[i + 1]
            new_layer.append(hash_data(combined))
        layer = new_layer

    return layer[0]


def generate_proof(items: List[Any], target_index: int) -> List[str]:
    """
    Generate Merkle proof for item at target_index
    Returns list of sibling hashes for verification
    """
    if not items or target_index >= len(items):
        return []

    # Hash all items
    layer = [hash_data(item) for item in items]

    proof = []
    index = target_index

    while len(layer) > 1:
        # Duplicate last if odd
        if len(layer) % 2 == 1:
            layer.append(layer[-1])

        # Find sibling
        if index % 2 == 0:
            sibling_index = index + 1
        else:
            sibling_index = index - 1

        if sibling_index < len(layer):
            proof.append(layer[sibling_index])

        # Build new layer
        new_layer = []
        for i in range(0, len(layer), 2):
            combined = layer[i] + layer[i + 1]
            new_layer.append(hash_data(combined))
        layer = new_layer

        index = index // 2

    return proof


def verify_proof(item: Any, proof: List[str], expected_root: str, target_index: int) -> bool:
    """
    Verify that item is included in Merkle tree with given root
    """
    current_hash = hash_data(item)
    index = target_index

    for sibling_hash in proof:
        if index % 2 == 0:
            combined = current_hash + sibling_hash
        else:
            combined = sibling_hash + current_hash
        current_hash = hash_data(combined)
        index = index // 2

    return current_hash == expected_root


def merkle_root_from_proof(item: Any, proof: List[str], target_index: int) -> str:
    """
    Reconstruct Merkle root from item and proof
    """
    current_hash = hash_data(item)
    index = target_index

    for sibling_hash in proof:
        if index % 2 == 0:
            combined = current_hash + sibling_hash
        else:
            combined = sibling_hash + current_hash
        current_hash = hash_data(combined)
        index = index // 2

    return current_hash
