# consensus/finality.py
"""
Finality Engine — Casper FFG with event-driven evaluation
Finality is checked immediately when votes are added
"""

from typing import Dict, Set, Optional


class FinalityEngine:
    """
    Casper FFG finality with event-driven evaluation:
    - Every vote triggers immediate justification and finality check
    - Epoch N is finalized when epoch N and N+1 are both justified
    """

    def __init__(self, threshold_ratio: float = 2/3):
        self.threshold_ratio = threshold_ratio
        self.epoch_votes: Dict[int, Dict[str, int]] = {}
        self.total_stake = 0
        
        # State tracking
        self.justified_epochs: Set[int] = set()
        self.finalized_epochs: Set[int] = set()
        self.justified_blocks: Dict[int, str] = {}

    def set_total_stake(self, total_stake: int):
        self.total_stake = total_stake

    def add_vote(self, epoch: int, block_hash: str, weight: int):
        """
        Add validator vote and IMMEDIATELY trigger evaluation.
        This is critical for correct Casper FFG behavior.
        """
        if epoch not in self.epoch_votes:
            self.epoch_votes[epoch] = {}
        self.epoch_votes[epoch][block_hash] = self.epoch_votes[epoch].get(block_hash, 0) + weight

        # 🔥 CRITICAL: Evaluate immediately (event-driven)
        self._evaluate(epoch)

    def _get_threshold(self) -> int:
        return int(self.total_stake * self.threshold_ratio)

    def _get_best_block(self, epoch: int) -> Optional[tuple]:
        if epoch not in self.epoch_votes:
            return None
        return max(self.epoch_votes[epoch].items(), key=lambda x: x[1])

    def _evaluate(self, epoch: int):
        """
        Evaluate justification and finalization for epoch.
        This is called every time a vote is added.
        """
        # Check if epoch can be justified
        best = self._get_best_block(epoch)
        if not best:
            return

        block_hash, weight = best
        threshold = self._get_threshold()

        if weight >= threshold:
            # Justify epoch
            if epoch not in self.justified_epochs:
                self.justified_epochs.add(epoch)
                self.justified_blocks[epoch] = block_hash

            # Check if previous epoch can be finalized
            prev_epoch = epoch - 1
            if prev_epoch in self.justified_epochs:
                # Casper FFG rule: epoch N is finalized when N and N+1 are justified
                if prev_epoch not in self.finalized_epochs:
                    self.finalized_epochs.add(prev_epoch)

    def try_justify(self, epoch: int) -> bool:
        """Explicit justify check (for manual calls)"""
        self._evaluate(epoch)
        return epoch in self.justified_epochs

    def try_finalize(self, epoch: int) -> bool:
        """Explicit finalize check (for manual calls)"""
        self._evaluate(epoch + 1)  # Check if next epoch is justified
        return epoch in self.finalized_epochs

    def update(self, epoch: int) -> dict:
        """
        Update finality state for epoch.
        Returns current state after evaluation.
        """
        self._evaluate(epoch)
        
        result = {
            "epoch": epoch,
            "justified": epoch in self.justified_epochs,
            "finalized": epoch in self.finalized_epochs,
            "justified_block": self.justified_blocks.get(epoch),
            "finalized_epochs": sorted(list(self.finalized_epochs))
        }
        return result

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
