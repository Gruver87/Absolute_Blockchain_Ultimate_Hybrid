# consensus/engine_slashing.py
"""
Consensus Engine с поддержкой слэшинга
"""

from typing import Dict, Optional, Any
from consensus.lmd import LMDTable
from consensus.ghost import select_head, get_cumulative_weight
from consensus.finality_beacon import BeaconFinality
from consensus.slashing import SlashingEngine
from consensus.epoch import EpochManager


class ConsensusEngineSlashing:
    """
    Consensus engine с экономической защитой:
    - LMD-GHOST fork choice
    - Beacon finality (Casper FFG)
    - Slashing detection (double vote + surround vote)
    """

    def __init__(self, epoch_size: int = 3):
        self.lmd = LMDTable()
        self.finality = BeaconFinality(epoch_size)
        self.slashing = SlashingEngine()
        self.epoch_mgr = EpochManager(epoch_size)
        self._block_tree: Dict[str, Dict] = {}
        self._blocks: Dict[str, Dict] = {}
        self._slot = 0

    def add_validator(self, validator_id: str, stake: int = 100):
        """Добавляет валидатора во все подсистемы"""
        self.lmd.add_validator(validator_id, stake)
        self.slashing.register_validator(validator_id, stake)
        self.finality.set_total_stake(self.slashing.get_total_active_stake())

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

    def on_attestation(self, validator_id: str, block_hash: str, slot: int) -> bool:
        """
        Обработка аттестации с проверкой слэшинга
        Returns: True если голос принят, False если валидатор слэшнут
        """
        # Slot-based double-vote detection (one attestation per slot)
        slashing_ok = self.slashing.add_vote(validator_id, slot, block_hash)

        if not slashing_ok:
            # Валидатор слэшнут — его голоса больше не учитываются
            return False

        # Обновляем LMD только если валидатор не слэшнут
        stake = self.slashing.get_stake(validator_id)
        if stake > 0:
            self.lmd.update(validator_id, block_hash, slot)

            # Обновляем финализацию
            block = self._blocks.get(block_hash)
            if block:
                epoch_f = self.epoch_mgr.get_epoch(block.get("number", 0))
                self.finality.add_vote(validator_id, block_hash, slot, stake)

        # Обновляем total stake для финализации
        self.finality.set_total_stake(self.slashing.get_total_active_stake())

        return True

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

    def is_finalized(self, block_hash: str) -> bool:
        block = self._blocks.get(block_hash)
        if not block:
            return False
        return self.finality.is_finalized(block.get("number", 0))

    def get_stats(self) -> dict:
        lmd_stats = self.lmd.get_stats()
        finality_stats = self.finality.get_stats()
        slashing_stats = self.slashing.get_stats()
        return {
            "validators": lmd_stats["validators"],
            "active_votes": lmd_stats["active_votes"],
            "active_validators": slashing_stats.get("total_validators", 0) - slashing_stats.get("slashed_count", 0),
            "active_stake": slashing_stats["active_stake"],
            "slashed_count": slashing_stats["slashed_count"],
            "total_stake": slashing_stats["active_stake"],
            "slashed_validators": slashing_stats["slashed_validators"],
            "slashed_stake": slashing_stats["slashed_stake"],
            "blocks": len(self._blocks),
            "head_hash": self.get_head(),
            "head_height": self.get_head_height(),
            "justified_epochs": finality_stats["justified_epochs"],
            "finalized_epochs": finality_stats["finalized_epochs"]
        }

    def get_slashing_stats(self) -> dict:
        return self.slashing.get_stats()

    def get_slashing_info(self) -> dict:
        stats = self.get_slashing_stats()
        stats["count"] = stats.get("slashed_count", stats.get("slashed_validators", 0))
        stats["slashed"] = list(self.slashing.slashed)
        reasons = {}
        for event in self.slashing.get_events():
            reasons[event.validator] = event.reason.upper()
        stats["reasons"] = reasons
        return stats

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

    def get_cumulative_weight(self, block_hash: str) -> int:
        weights = self.lmd.get_weights()
        return get_cumulative_weight(block_hash, self._block_tree, weights)
