# consensus/validator_selection.py
"""
Validator Selection — RANDAO-style randomness for proposer selection
"""

import hashlib
import random
from typing import Dict, List, Optional


class ValidatorSelection:
    """
    Simplified RANDAO-style validator selection
    - Randomness seed updated with each block
    - Deterministic but pseudo-random proposer selection
    - Epoch-based validator shuffling
    """

    def __init__(self, initial_seed: str = None):
        # Используем хэш от "genesis" вместо строки
        if initial_seed is None:
            initial_seed = hashlib.sha256(b"genesis").hexdigest()
        self.random_seed = initial_seed
        self.epoch = 0

    def update_seed(self, block_hash: str):
        """
        RANDAO-style mixing of entropy from block hashes
        Each block adds randomness to the seed
        """
        self.random_seed = hashlib.sha256(
            (self.random_seed + block_hash).encode()
        ).hexdigest()

    def set_epoch(self, epoch: int):
        self.epoch = epoch

    def get_seed(self) -> str:
        return self.random_seed

    def _get_seed_int(self) -> int:
        """Преобразует seed в integer для вычислений"""
        return int(self.random_seed, 16)

    def select_proposer(self, validators: Dict[str, int], slot: int) -> Optional[str]:
        """
        Deterministic but pseudo-random proposer selection
        Based on current randomness seed and slot number
        """
        if not validators:
            return None

        # Mix seed with slot for unique selection per slot
        seed_int = self._get_seed_int()
        slot_mix = seed_int + slot + (self.epoch * 1000)

        validator_list = list(validators.keys())
        index = slot_mix % len(validator_list)

        return validator_list[index]

    def select_proposer_weighted(self, validators: Dict[str, int], slot: int) -> Optional[str]:
        """
        Weighted proposer selection (stake-based probability)
        Validators with higher stake have higher chance to be selected
        """
        if not validators:
            return None

        seed_int = self._get_seed_int()
        slot_mix = seed_int + slot + (self.epoch * 1000)

        total_stake = sum(validators.values())
        if total_stake == 0:
            return list(validators.keys())[slot_mix % len(validators)]

        target = slot_mix % total_stake
        cumulative = 0

        for validator, stake in validators.items():
            cumulative += stake
            if cumulative > target:
                return validator

        return list(validators.keys())[0]

    def shuffle_validators(self, validators: Dict[str, int]) -> Dict[str, int]:
        """
        Epoch-based validator shuffling (like Ethereum committee shuffle)
        Deterministic but unpredictable order based on current seed
        """
        seed_int = self._get_seed_int()
        items = list(validators.items())

        # Deterministic shuffle using RNG with fixed seed
        rng = random.Random(seed_int + self.epoch)
        rng.shuffle(items)

        return dict(items)

    def get_committee(self, validators: Dict[str, int], committee_size: int) -> List[str]:
        """
        Select random committee of validators (for attestation aggregation)
        """
        if not validators:
            return []

        validator_list = list(validators.keys())
        seed_int = self._get_seed_int()
        rng = random.Random(seed_int + self.epoch)
        rng.shuffle(validator_list)

        return validator_list[:min(committee_size, len(validator_list))]

    def get_stats(self) -> dict:
        return {
            "epoch": self.epoch,
            "seed": self.random_seed[:16] + "...",
            "seed_length": len(self.random_seed)
        }
