# consensus/engine_refactored.py
"""
Consensus Engine — Orchestrator
Separates LMD (votes) from GHOST (fork choice)
"""

from typing import Dict, Optional, List, Any
from consensus.lmd import LMDTable
from consensus.ghost import select_head, get_cumulative_weight


class ConsensusEngine:
    """
    Ethereum-style consensus separation:
    - LMD table for votes
    - Pure GHOST for fork choice
    - Deterministic head selection
    """

    def __init__(self):
        self.lmd = LMDTable()
        self._block_tree: Dict[str, Dict] = {}
        self._blocks: Dict[str, Dict] = {}
        self._slot = 0

    # =========================================================
    # VALIDATORS
    # =========================================================
    def add_validator(self, validator_id: str, stake: int = 100):
        self.lmd.add_validator(validator_id, stake)

    def get_validator_stake(self, validator_id: str) -> int:
        # For compatibility
        return 100  # Simplified

    # =========================================================
    # BLOCKS
    # =========================================================
    def add_block(self, block: Dict):
        """Add block to fork choice tree"""
        block_hash = block.get("hash") or block.get("block_hash")
        parent_hash = block.get("parent_hash") or block.get("parent")

        self._blocks[block_hash] = block

        if block_hash not in self._block_tree:
            self._block_tree[block_hash] = {
                "parent": parent_hash,
                "children": [],
                "number": block.get("number", 0)
            }

        if parent_hash:
            if parent_hash not in self._block_tree:
                self._block_tree[parent_hash] = {"parent": None, "children": [], "number": 0}
            if block_hash not in self._block_tree[parent_hash]["children"]:
                self._block_tree[parent_hash]["children"].append(block_hash)

    # =========================================================
    # ATTESTATIONS (LMD)
    # =========================================================
    def on_attestation(self, validator_id: str, block_hash: str, slot: int):
        """Process attestation — only updates LMD table"""
        return self.lmd.update(validator_id, block_hash, slot)

    # =========================================================
    # HEAD SELECTION (PURE GHOST)
    # =========================================================
    def get_head(self) -> Optional[str]:
        """Get current chain head using pure GHOST"""
        weights = self.lmd.get_weights()
        return select_head(self._block_tree, weights)

    def get_head_block(self) -> Optional[Dict]:
        head_hash = self.get_head()
        if head_hash:
            return self._blocks.get(head_hash)
        return None

    def get_head_height(self) -> int:
        head = self.get_head_block()
        return head.get("number", 0) if head else 0

    def get_cumulative_weight(self, block_hash: str) -> int:
        """Get cumulative weight of a block"""
        from consensus.ghost import get_cumulative_weight
        weights = self.lmd.get_weights()
        return get_cumulative_weight(block_hash, self._block_tree, weights)

    # =========================================================
    # STATS
    # =========================================================
    def get_stats(self) -> dict:
        lmd_stats = self.lmd.get_stats()
        return {
            "validators": lmd_stats["validators"],
            "active_votes": lmd_stats["active_votes"],
            "total_stake": lmd_stats["total_stake"],
            "blocks": len(self._blocks),
            "tree_nodes": len(self._block_tree),
            "head_hash": self.get_head(),
            "head_height": self.get_head_height()
        }

    def print_tree(self, block_hash: str = None, indent: int = 0):
        """Print fork choice tree with weights"""
        weights = self.lmd.get_weights()

        if block_hash is None:
            # Find genesis
            for h, data in self._block_tree.items():
                if data.get("parent") is None:
                    block_hash = h
                    break

        if not block_hash or block_hash not in self._block_tree:
            print("Empty tree")
            return

        prefix = "  " * indent
        weight = weights.get(block_hash, 0)
        cum = self.get_cumulative_weight(block_hash)
        block = self._blocks.get(block_hash, {})
        block_num = block.get("number", "?")
        print(f"{prefix}📦 #{block_num} ({block_hash[:8]}...) weight: {weight} | cum: {cum}")

        for child in self._block_tree.get(block_hash, {}).get("children", []):
            self.print_tree(child, indent + 1)

