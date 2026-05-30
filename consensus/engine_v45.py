# consensus/engine_v45.py
"""
Consensus Engine v45 — LMD-GHOST + Casper FFG + Slashing + RANDAO
"""

from typing import Dict, Optional, Any
from consensus.lmd import LMDTable
from consensus.ghost import select_head
from consensus.finality_beacon import BeaconFinality
from consensus.slashing import SlashingEngine
from consensus.validator_selection import ValidatorSelection
from consensus.epoch import EpochManager


class ConsensusEngineV45:
    """
    Full Ethereum consensus stack:
    - LMD-GHOST fork choice
    - Casper FFG finality
    - Slashing (double vote detection)
    - RANDAO validator selection
    """

    def __init__(self, epoch_size: int = 3):
        self.lmd = LMDTable()
        self.finality = BeaconFinality(epoch_size)
        self.slashing = SlashingEngine()
        self.selector = ValidatorSelection()
        self.epoch_mgr = EpochManager(epoch_size)
        self._block_tree: Dict[str, Dict] = {}
        self._blocks: Dict[str, Dict] = {}
        self._validators: Dict[str, int] = {}
        self._slot = 0
        self._current_epoch = 0

    def add_validator(self, validator_id: str, stake: int = 100):
        """Добавляет валидатора"""
        self._validators[validator_id] = stake
        self.lmd.add_validator(validator_id, stake)
        self._update_total_stake()

    def _update_total_stake(self):
        """Обновляет total stake для финализации"""
        active_stake = self._get_active_stake()
        self.finality.set_total_stake(active_stake)

    def _get_active_stake(self) -> int:
        """Получает активный стейк (только не слэшнутые)"""
        active = self.slashing.get_active_validators(self._validators)
        return sum(active.values())

    def get_active_validators(self) -> Dict[str, int]:
        """Возвращает только активных (не слэшнутых) валидаторов"""
        return self.slashing.get_active_validators(self._validators)

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

        # Update randomness seed with block hash
        self.selector.update_seed(block_hash)

    def on_attestation(self, validator_id: str, block_hash: str, slot: int) -> bool:
        """Обработка аттестации с проверкой слэшинга"""
        epoch = self.epoch_mgr.get_epoch(slot)

        # Check epoch boundary for validator shuffling
        if epoch != self._current_epoch:
            self._current_epoch = epoch
            self.selector.set_epoch(epoch)
            # Shuffle validators at epoch boundary (optional)
            # self._validators = self.selector.shuffle_validators(self._validators)

        # Slashing first
        slashing_ok = self.slashing.add_vote(validator_id, epoch, block_hash)

        if not slashing_ok or self.slashing.is_slashed(validator_id):
            return False

        # Get active stake
        active_validators = self.get_active_validators()
        stake = active_validators.get(validator_id, 0)

        if stake == 0:
            return False

        # LMD update
        self.lmd.update(validator_id, block_hash, slot)

        # Finality update
        block = self._blocks.get(block_hash)
        if block:
            epoch_f = self.epoch_mgr.get_epoch(block.get("number", 0))
            self.finality.add_vote(validator_id, block_hash, slot, stake)

        self._update_total_stake()

        return True

    def get_proposer(self, slot: int) -> Optional[str]:
        """Возвращает proposer для данного слота"""
        active_validators = self.get_active_validators()
        if not active_validators:
            return None
        return self.selector.select_proposer(active_validators, slot)

    def get_proposer_weighted(self, slot: int) -> Optional[str]:
        """Возвращает proposer с учётом веса стейка"""
        active_validators = self.get_active_validators()
        if not active_validators:
            return None
        return self.selector.select_proposer_weighted(active_validators, slot)

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
        selector_stats = self.selector.get_stats()
        return {
            "validators": len(self._validators),
            "active_validators": len(self.get_active_validators()),
            "total_stake": sum(self._validators.values()),
            "active_stake": self._get_active_stake(),
            "slashed_count": slashing_stats["slashed_count"],
            "blocks": len(self._blocks),
            "head_hash": self.get_head(),
            "head_height": self.get_head_height(),
            "justified_epochs": finality_stats["justified_epochs"],
            "finalized_epochs": finality_stats["finalized_epochs"],
            "random_seed": selector_stats["seed"]
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
        block = self._blocks.get(block_hash, {})
        block_num = block.get("number", "?")
        is_final = "🔒" if self.is_finalized(block_hash) else "📦"
        print(f"{prefix}{is_final} #{block_num} ({block_hash[:8]}...) weight: {weight}")

        for child in self._block_tree.get(block_hash, {}).get("children", []):
            self.print_tree(child, indent + 1)
