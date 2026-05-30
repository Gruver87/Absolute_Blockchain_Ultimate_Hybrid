# consensus/engine_beacon.py
"""
Consensus Engine with Beacon Chain Finality
"""

from typing import Dict, List, Optional, Any
from consensus.lmd import LMDTable
from consensus.ghost import select_head, get_cumulative_weight
from consensus.finality_beacon import BeaconFinality
from consensus.epoch import EpochManager


class ConsensusEngineBeacon:
    """
    Full Ethereum consensus with correct Beacon Chain finality
    """

    def __init__(self, epoch_size: int = 3):
        self.lmd = LMDTable()
        self.finality = BeaconFinality(epoch_size)
        self.epoch_mgr = EpochManager(epoch_size)
        self._block_tree: Dict[str, Dict] = {}
        self._blocks: Dict[str, Dict] = {}
        self._slot = 0

    def add_validator(self, validator_id: str, stake: int = 100):
        self.lmd.add_validator(validator_id, stake)
        self.finality.set_total_stake(self.lmd.get_stats()["total_stake"])

    def add_block(self, block: Dict):
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

    def on_attestation(self, validator_id: str, block_hash: str, slot: int):
        """Process attestation — updates LMD and finality"""
        result = self.lmd.update(validator_id, block_hash, slot)
        
        if result:
            # Get stake for this validator
            stake = self.lmd.validator_stake.get(validator_id, 0)
            self.finality.add_vote(validator_id, block_hash, slot, stake)
        
        return result

    def get_head(self) -> Optional[str]:
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
        weights = self.lmd.get_weights()
        return get_cumulative_weight(block_hash, self._block_tree, weights)

    def is_finalized(self, block_hash: str) -> bool:
        block = self._blocks.get(block_hash)
        if not block:
            return False
        return self.finality.is_finalized(block.get("number", 0))

    def get_finality_state(self) -> dict:
        return self.finality.get_state()

    def get_stats(self) -> dict:
        lmd_stats = self.lmd.get_stats()
        finality_stats = self.finality.get_stats()
        return {
            "validators": lmd_stats["validators"],
            "active_votes": lmd_stats["active_votes"],
            "total_stake": lmd_stats["total_stake"],
            "blocks": len(self._blocks),
            "head_hash": self.get_head(),
            "head_height": self.get_head_height(),
            "justified_epochs": finality_stats["justified_epochs"],
            "finalized_epochs": finality_stats["finalized_epochs"],
            "justified_list": finality_stats["justified_list"],
            "finalized_list": finality_stats["finalized_list"]
        }

    def print_tree(self, block_hash: str = None, indent: int = 0):
        weights = self.lmd.get_weights()

        if block_hash is None:
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
        is_final = "🔒" if self.is_finalized(block_hash) else "📦"
        print(f"{prefix}{is_final} #{block_num} ({block_hash[:8]}...) weight: {weight} | cum: {cum}")

        for child in self._block_tree.get(block_hash, {}).get("children", []):
            self.print_tree(child, indent + 1)
