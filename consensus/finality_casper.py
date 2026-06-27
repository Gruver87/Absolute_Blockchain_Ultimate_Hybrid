# consensus/finality_casper.py
"""
Casper FFG Finality — Two-Step Rule
Epoch N is finalized ONLY when epoch N+1 is also justified
"""

from typing import Dict, Set, Optional


class CasperFinality:
    """
    Correct Casper FFG implementation:
    - Justified epochs are tracked as a set
    - Epoch N becomes finalized when epoch N+1 is justified
    - Finality requires 2 consecutive justified epochs
    """

    def __init__(self, threshold_ratio: float = 2/3):
        self.threshold_ratio = threshold_ratio
        self.epoch_votes: Dict[int, Dict[str, int]] = {}
        self.total_stake = 0
        
        # Track justified epochs (history matters!)
        self.justified_epochs: Set[int] = set()
        self.finalized_epochs: Set[int] = set()
        self.justified_blocks: Dict[int, str] = {}

    def set_total_stake(self, total_stake: int):
        self.total_stake = total_stake

    def add_vote(self, epoch: int, block_hash: str, weight: int):
        """Add validator vote and evaluate justification/finalization"""
        if epoch not in self.epoch_votes:
            self.epoch_votes[epoch] = {}
        self.epoch_votes[epoch][block_hash] = self.epoch_votes[epoch].get(block_hash, 0) + weight

        self._evaluate(epoch)

    def _get_threshold(self) -> int:
        return int(self.total_stake * self.threshold_ratio)

    def _get_best_block(self, epoch: int) -> Optional[tuple]:
        if epoch not in self.epoch_votes:
            return None
        return max(self.epoch_votes[epoch].items(), key=lambda x: x[1])

    def _justify_epoch(self, epoch: int, block_hash: str):
        """Mark epoch as justified"""
        if epoch not in self.justified_epochs:
            self.justified_epochs.add(epoch)
            self.justified_blocks[epoch] = block_hash

    def _try_finalize(self, epoch: int):
        """
        Casper FFG finalization rule:
        Epoch N is finalized if:
        - Epoch N is justified
        - Epoch N+1 is justified
        
        So when epoch N+1 becomes justified, epoch N should be finalized.
        """
        # Check if previous epoch can be finalized
        prev_epoch = epoch - 1
        if prev_epoch in self.justified_epochs and prev_epoch not in self.finalized_epochs:
            self.finalized_epochs.add(prev_epoch)

    def _evaluate(self, epoch: int):
        """
        Evaluate justification and finalization for epoch.
        Called every time a vote is added.
        """
        best = self._get_best_block(epoch)
        if not best:
            return

        block_hash, weight = best
        threshold = self._get_threshold()

        if weight >= threshold:
            # Justify current epoch
            self._justify_epoch(epoch, block_hash)
            
            # Try to finalize previous epoch (two-step rule)
            self._try_finalize(epoch)

    def update(self, epoch: int) -> dict:
        """Manual update (for compatibility)"""
        self._evaluate(epoch)
        return self.get_state(epoch)

    def get_state(self, epoch: int) -> dict:
        """Get current finality state"""
        return {
            "epoch": epoch,
            "justified": epoch in self.justified_epochs,
            "finalized": epoch in self.finalized_epochs,
            "justified_block": self.justified_blocks.get(epoch),
            "justified_epochs": sorted(list(self.justified_epochs)),
            "finalized_epochs": sorted(list(self.finalized_epochs))
        }

    def is_finalized(self, block_number: int, epoch_mgr) -> bool:
        """Check if a block is in a finalized epoch"""
        epoch = epoch_mgr.get_epoch(block_number)
        return epoch in self.finalized_epochs

    def get_finalized_epochs(self) -> Set[int]:
        return self.finalized_epochs

    def get_justified_epochs(self) -> Set[int]:
        return self.justified_epochs

    def get_stats(self) -> dict:
        return {
            "total_stake": self.total_stake,
            "justified_epochs": len(self.justified_epochs),
            "finalized_epochs": len(self.finalized_epochs),
            "justified_list": sorted(list(self.justified_epochs)),
            "finalized_list": sorted(list(self.finalized_epochs))
        }
