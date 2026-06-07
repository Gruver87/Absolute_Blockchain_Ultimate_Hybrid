# consensus/slashing.py
"""
Slashing Engine — наказание валидаторов за нарушение консенсуса
Double vote detection (LMD violation)
"""

from typing import Dict, Set, Optional


class SlashingEngine:
    """
    Handles validator misbehavior detection:
    - Double vote (LMD violation)
    - Basic penalty tracking
    """

    def __init__(self):
        # validator -> (epoch -> block)
        self.votes: Dict[str, Dict[int, str]] = {}
        # slashed validators
        self.slashed: Set[str] = set()
        # info
        self.reasons: Dict[str, str] = {}

    def is_slashed(self, validator: str) -> bool:
        return validator in self.slashed

    def add_vote(self, validator: str, epoch: int, block: str) -> bool:
        """
        Add vote and check for double vote.
        Returns True if vote accepted, False if validator already slashed.
        """
        if self.is_slashed(validator):
            return False

        if validator not in self.votes:
            self.votes[validator] = {}

        # already voted in this epoch?
        if epoch in self.votes[validator]:
            old_block = self.votes[validator][epoch]
            if old_block != block:
                self.slash(validator, f"DOUBLE_VOTE epoch={epoch} (voted {old_block} and {block})")
                return False

        self.votes[validator][epoch] = block
        return True

    def slash(self, validator: str, reason: str):
        """Slash validator — remove from consensus"""
        self.slashed.add(validator)
        self.reasons[validator] = reason
        print(f"🔥 Validator {validator} SLASHED! Reason: {reason}")

    def get_active_validators(self, validators: dict) -> dict:
        """
        Returns only non-slashed validators
        """
        return {
            v: stake
            for v, stake in validators.items()
            if v not in self.slashed
        }

    def get_active_stake(self, validators: dict) -> int:
        """Returns total active stake (non-slashed)"""
        active = self.get_active_validators(validators)
        return sum(active.values())

    def get_slashing_info(self) -> dict:
        return {
            "slashed": list(self.slashed),
            "reasons": self.reasons,
            "count": len(self.slashed)
        }

    def get_stats(self) -> dict:
        return {
            "slashed_count": len(self.slashed),
            "slashed_validators": list(self.slashed),
            "reasons": self.reasons
        }

    def clear(self):
        """Reset slashing state (for testing)"""
        self.votes.clear()
        self.slashed.clear()
        self.reasons.clear()
