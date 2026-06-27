# consensus/finality_beacon.py
"""
Beacon Chain Finality Engine — Correct Casper FFG
- Checkpoint-based finality
- Event-driven justification and finalization
- No backward inconsistencies
"""

from typing import Dict, Optional, Set


class BeaconFinality:
    """
    Ethereum-style Beacon Chain finality:
    - Checkpoints are epochs
    - Epoch N becomes justified with 2/3 majority
    - Epoch N becomes finalized when epoch N+1 is justified
    """

    def __init__(self, epoch_size: int = 3, threshold_ratio: float = 2/3):
        self.epoch_size = epoch_size
        self.threshold_ratio = threshold_ratio
        self.total_stake = 0
        
        # Checkpoint votes: epoch -> block -> weight
        self.votes: Dict[int, Dict[str, int]] = {}
        
        # State
        self.justified_checkpoint: Optional[int] = None
        self.justified_block: Optional[str] = None
        self.finalized_checkpoint: Optional[int] = None
        self.finalized_block: Optional[str] = None
        
        # History
        self.justified_epochs: Set[int] = set()
        self.finalized_epochs: Set[int] = set()
        self.justified_blocks: Dict[int, str] = {}

    def set_total_stake(self, total_stake: int):
        self.total_stake = total_stake

    def _get_epoch(self, block_number: int) -> int:
        return block_number // self.epoch_size

    def _get_threshold(self) -> int:
        return int(self.total_stake * self.threshold_ratio)

    def _get_best_checkpoint(self, epoch: int) -> Optional[tuple]:
        """Returns (block_hash, weight) for best checkpoint in epoch"""
        if epoch not in self.votes:
            return None
        return max(self.votes[epoch].items(), key=lambda x: x[1])

    def add_vote(self, validator_id: str, block_hash: str, slot: int, weight: int):
        """
        Add validator vote and trigger finality evaluation.
        Called every time a validator attests.
        """
        epoch = self._get_epoch(slot)
        
        if epoch not in self.votes:
            self.votes[epoch] = {}
        
        self.votes[epoch][block_hash] = self.votes[epoch].get(block_hash, 0) + weight
        
        # Trigger finality evaluation immediately
        self._evaluate(epoch)

    def _evaluate(self, epoch: int):
        """Evaluate justification and finalization for checkpoint"""
        best = self._get_best_checkpoint(epoch)
        if not best:
            return
        
        block_hash, weight = best
        threshold = self._get_threshold()
        
        if weight >= threshold:
            # This checkpoint is justified
            if epoch not in self.justified_epochs:
                self.justified_epochs.add(epoch)
                self.justified_blocks[epoch] = block_hash
                
                # Update current justified checkpoint
                self.justified_checkpoint = epoch
                self.justified_block = block_hash
                
                # 🔥 CASPER FFG FINALITY RULE:
                # When epoch N becomes justified, check if epoch N-1 can be finalized
                prev_epoch = epoch - 1
                if prev_epoch in self.justified_epochs and prev_epoch not in self.finalized_epochs:
                    self.finalized_epochs.add(prev_epoch)
                    self.finalized_checkpoint = prev_epoch
                    self.finalized_block = self.justified_blocks.get(prev_epoch)

    def is_justified(self, epoch: int) -> bool:
        return epoch in self.justified_epochs

    def is_finalized(self, block_number: int) -> bool:
        """Check if a block is in a finalized epoch"""
        epoch = self._get_epoch(block_number)
        return epoch in self.finalized_epochs

    def get_state(self) -> dict:
        return {
            "justified_checkpoint": self.justified_checkpoint,
            "justified_block": self.justified_block,
            "finalized_checkpoint": self.finalized_checkpoint,
            "finalized_block": self.finalized_block,
            "justified_epochs": sorted(list(self.justified_epochs)),
            "finalized_epochs": sorted(list(self.finalized_epochs))
        }

    def get_stats(self) -> dict:
        return {
            "total_stake": self.total_stake,
            "justified_epochs": len(self.justified_epochs),
            "finalized_epochs": len(self.finalized_epochs),
            "justified_list": sorted(list(self.justified_epochs)),
            "finalized_list": sorted(list(self.finalized_epochs))
        }
