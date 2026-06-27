#!/usr/bin/env python3
"""GHOST fork choice on deep linear chains."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from consensus.ghost import get_cumulative_weight, select_head


def test_ghost_deep_linear_chain_no_recursion_error():
    tree = {}
    weights = {}
    prev = None
    for i in range(2000):
        h = f"block_{i:04d}"
        tree[h] = {"parent": prev, "number": i, "children": []}
        if prev:
            tree[prev]["children"].append(h)
        weights[h] = 1
        prev = h

    head = select_head(tree, weights)
    assert head == "block_1999"
    assert get_cumulative_weight("block_0000", tree, weights) == 2000
