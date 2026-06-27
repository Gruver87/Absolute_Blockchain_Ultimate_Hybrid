# consensus/epoch.py
"""
Epoch manager — группировка блоков для финализации
"""


class EpochManager:
    """Эпохи консенсуса — 32 блока (токеномика staking release)."""

    def __init__(self, epoch_size: int = 32):
        self.epoch_size = epoch_size
        self.block_to_epoch = {}

    def get_epoch(self, block_number: int) -> int:
        """Returns epoch number for given block number"""
        return block_number // self.epoch_size

    def is_epoch_boundary(self, block_number: int) -> bool:
        """Check if block is at epoch boundary"""
        return block_number % self.epoch_size == 0

    def get_epoch_start(self, epoch: int) -> int:
        """Returns first block number of epoch"""
        return epoch * self.epoch_size

    def get_epoch_end(self, epoch: int) -> int:
        """Returns last block number of epoch"""
        return (epoch + 1) * self.epoch_size - 1

    def get_blocks_in_epoch(self, blocks: dict, epoch: int) -> list:
        """Returns all blocks belonging to an epoch"""
        start = self.get_epoch_start(epoch)
        end = self.get_epoch_end(epoch)
        return [b for b in blocks.values() if start <= b.get("number", 0) <= end]
