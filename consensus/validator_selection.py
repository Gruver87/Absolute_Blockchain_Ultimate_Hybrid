# consensus/validator_selection.py
"""
Validator Selection — deterministic RANDAO-style proposer and committee selection.
"""

import hashlib
from typing import Dict, List, Optional


class ValidatorSelection:
    """
    Deterministic RANDAO-style validator selection.
    - Seed is mixed with every finalized/local block hash.
    - Proposer and committee selection are hash-ranked, not Python RNG based.
    - Validator ordering is canonical, so all nodes agree independent of dict order.
    """

    def __init__(self, initial_seed: str = None):
        # Используем хэш от "genesis" вместо строки
        if initial_seed is None:
            initial_seed = hashlib.sha256(b"genesis").hexdigest()
        self.entropy_seed = initial_seed
        self.epoch = 0

    def update_seed(self, block_hash: str):
        """
        RANDAO-style mixing of entropy from block hashes
        Each block contributes deterministic entropy to the seed.
        """
        self.entropy_seed = hashlib.sha256(
            (self.entropy_seed + block_hash).encode()
        ).hexdigest()

    def set_epoch(self, epoch: int):
        self.epoch = epoch

    def get_seed(self) -> str:
        return self.entropy_seed

    def _hash_int(self, *parts: object) -> int:
        payload = "|".join(str(part) for part in (self.entropy_seed, self.epoch, *parts))
        return int(hashlib.sha256(payload.encode()).hexdigest(), 16)

    def _canonical_validators(self, validators: Dict[str, int]) -> List[tuple]:
        return sorted(
            ((str(addr), max(0, int(stake or 0))) for addr, stake in validators.items()),
            key=lambda item: item[0],
        )

    def select_proposer(self, validators: Dict[str, int], slot: int) -> Optional[str]:
        """
        Deterministic hash-ranked proposer selection.
        Equal validator sets produce the same proposer on every node.
        """
        if not validators:
            return None

        ranked = sorted(
            self._canonical_validators(validators),
            key=lambda item: self._hash_int("proposer", slot, item[0]),
        )
        return ranked[0][0]

    def select_proposer_weighted(self, validators: Dict[str, int], slot: int) -> Optional[str]:
        """
        Deterministic stake-weighted proposer selection.
        Higher stake expands the validator's interval in the canonical stake range.
        """
        if not validators:
            return None

        canonical = self._canonical_validators(validators)
        total_stake = sum(stake for _, stake in canonical)

        if total_stake == 0:
            return self.select_proposer(validators, slot)

        target = self._hash_int("weighted-proposer", slot) % total_stake
        cumulative = 0

        for validator, stake in canonical:
            cumulative += stake
            if cumulative > target:
                return validator

        return canonical[0][0]

    def shuffle_validators(self, validators: Dict[str, int]) -> Dict[str, int]:
        """
        Epoch-based deterministic validator shuffling.
        Uses hash ranking instead of Python's process-local RNG implementation.
        """
        items = sorted(
            self._canonical_validators(validators),
            key=lambda item: self._hash_int("shuffle", item[0]),
        )

        return dict(items)

    def get_committee(self, validators: Dict[str, int], committee_size: int) -> List[str]:
        """
        Select deterministic hash-ranked committee for attestation aggregation.
        """
        if not validators:
            return []

        validator_list = [
            addr for addr, _ in sorted(
                self._canonical_validators(validators),
                key=lambda item: self._hash_int("committee", item[0]),
            )
        ]

        return validator_list[:min(committee_size, len(validator_list))]

    def get_stats(self) -> dict:
        return {
            "epoch": self.epoch,
            "seed": self.entropy_seed[:16] + "...",
            "seed_length": len(self.entropy_seed)
        }
