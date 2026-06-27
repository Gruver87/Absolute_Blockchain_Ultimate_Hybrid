# consensus/lmd.py
"""
LMD Table — Latest Message Driven
Only tracks latest attestation per validator
Strict slot-based overwrite
"""

from typing import Dict, Optional, Tuple


class LMDTable:
    """
    Strict LMD: only latest attestation per validator
    Slot-based: newer slot always overwrites older
    """

    def __init__(self):
        # validator -> (block_hash, slot)
        self.latest_vote: Dict[str, Tuple[str, int]] = {}
        self.validator_stake: Dict[str, int] = {}

    def add_validator(self, validator: str, stake: int = 100):
        self.validator_stake[validator] = stake

    def update(self, validator: str, block_hash: str, slot: int) -> bool:
        """Update latest vote for validator (strict LMD)"""
        if validator not in self.validator_stake:
            return False

        current = self.latest_vote.get(validator)

        # LMD rule: only update if slot is newer
        if current is None or slot > current[1]:
            self.latest_vote[validator] = (block_hash, slot)
            return True
        return False

    def get_weights(self) -> Dict[str, int]:
        """
        Calculate block weights from latest votes
        Each vote contributes validator's stake to its block
        """
        weights = {}
        for validator, (block_hash, _) in self.latest_vote.items():
            stake = self.validator_stake.get(validator, 0)
            weights[block_hash] = weights.get(block_hash, 0) + stake
        return weights

    def get_validator_vote(self, validator: str) -> Optional[Tuple[str, int]]:
        return self.latest_vote.get(validator)

    def get_stats(self) -> dict:
        return {
            "validators": len(self.validator_stake),
            "active_votes": len(self.latest_vote),
            "total_stake": sum(self.validator_stake.values()),
            "blocks_with_votes": len(self.get_weights())
        }
