# consensus/ghost.py
"""
Pure GHOST fork choice
No votes inside — only tree + weights

Hot path prefers abs_native kernels (ghost_select_head / ghost_cumulative_weight)
with a Python reference fallback for byte-aligned behavior.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from crypto import native


def _native_required() -> bool:
    return bool(native.native_crypto_status(required=False).get("required"))


def _tree_json(tree: Dict) -> str:
    return json.dumps(tree, separators=(",", ":"), ensure_ascii=False)


def _weights_json(weights: Dict[str, int]) -> str:
    return json.dumps(
        {str(k): int(v) for k, v in weights.items()},
        separators=(",", ":"),
        ensure_ascii=False,
    )


def get_cumulative_weight(block_hash: str, tree: Dict, weights: Dict[str, int]) -> int:
    """Cumulative weight of block and descendants (iterative — safe on long chains)."""
    if native.native_available() and hasattr(native, "ghost_cumulative_weight"):
        try:
            return int(
                native.ghost_cumulative_weight(
                    str(block_hash), _tree_json(tree), _weights_json(weights)
                )
            )
        except Exception:
            if _native_required():
                raise

    memo: Dict[str, int] = {}
    stack: List[tuple] = [(block_hash, False)]

    while stack:
        node, expanded = stack.pop()
        if expanded:
            total = weights.get(node, 0)
            for child in tree.get(node, {}).get("children", []):
                total += memo.get(child, 0)
            memo[node] = total
        else:
            stack.append((node, True))
            for child in reversed(tree.get(node, {}).get("children", [])):
                if child not in memo:
                    stack.append((child, False))

    return memo.get(block_hash, weights.get(block_hash, 0))


def select_head(tree: Dict, weights: Dict[str, int]) -> Optional[str]:
    """
    Pure GHOST: start from genesis, always pick child with highest cumulative weight
    """
    if native.native_available() and hasattr(native, "ghost_select_head"):
        try:
            head = native.ghost_select_head(_tree_json(tree), _weights_json(weights))
            return str(head) if head else None
        except Exception:
            if _native_required():
                raise

    if not tree:
        return None

    # Find genesis (block with no parent)
    genesis = None
    for block_hash, data in tree.items():
        if data.get("parent") is None:
            genesis = block_hash
            break

    if genesis is None:
        return None

    current = genesis
    visited = set()

    while current not in visited:
        visited.add(current)
        children = tree.get(current, {}).get("children", [])

        if not children:
            return current

        # Find child with highest cumulative weight
        best_child = None
        best_weight = -1

        for child in children:
            cum_weight = get_cumulative_weight(child, tree, weights)
            if cum_weight > best_weight:
                best_weight = cum_weight
                best_child = child
            elif cum_weight == best_weight and best_child is not None:
                # Tie-break: higher block number wins
                child_num = tree.get(child, {}).get("number", 0)
                best_num = tree.get(best_child, {}).get("number", 0)
                if child_num > best_num:
                    best_child = child
                elif child_num == best_num and child < best_child:
                    best_child = child

        if best_child is None:
            return current
        current = best_child

    return current


def get_chain_from_head(tree: Dict, weights: Dict[str, int]) -> List[str]:
    """Get full chain from genesis to head"""
    if native.native_available() and hasattr(native, "ghost_chain_from_head"):
        try:
            chain = native.ghost_chain_from_head(_tree_json(tree), _weights_json(weights))
            return [str(h) for h in chain]
        except Exception:
            if _native_required():
                raise

    head = select_head(tree, weights)
    if not head:
        return []

    chain = []
    current = head
    while current:
        chain.append(current)
        current = tree.get(current, {}).get("parent")
    return list(reversed(chain))
