# consensus/ghost.py
"""
Pure GHOST fork choice
No votes inside — only tree + weights
"""

from typing import Dict, List, Optional


def get_cumulative_weight(block_hash: str, tree: Dict, weights: Dict[str, int]) -> int:
    """Get cumulative weight of block and all its descendants"""
    total = weights.get(block_hash, 0)
    for child in tree.get(block_hash, {}).get("children", []):
        total += get_cumulative_weight(child, tree, weights)
    return total


def select_head(tree: Dict, weights: Dict[str, int]) -> Optional[str]:
    """
    Pure GHOST: start from genesis, always pick child with highest cumulative weight
    """
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
    head = select_head(tree, weights)
    if not head:
        return []

    chain = []
    current = head
    while current:
        chain.append(current)
        current = tree.get(current, {}).get("parent")
    return list(reversed(chain))
