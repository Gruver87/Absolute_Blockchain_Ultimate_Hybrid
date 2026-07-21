# consensus/validator_selection.py
"""
Validator Selection — deterministic RANDAO-style proposer and committee selection.
"""

from typing import Dict, List, Optional

from crypto import native


class ValidatorSelection:
    """
    Deterministic RANDAO-style validator selection.
    - Seed is mixed with every finalized/local block hash.
    - Proposer and committee selection are hash-ranked, not Python RNG based.
    - Validator ordering is canonical, so all nodes agree independent of dict order.
    """

    def __init__(self, initial_seed: str = None):
        if initial_seed is None:
            initial_seed = native.sha256_hex(b"genesis")
        self.entropy_seed = initial_seed
        self.epoch = 0

    def update_seed(self, block_hash: str):
        """
        RANDAO-style mixing of entropy from block hashes
        Each block contributes deterministic entropy to the seed.
        """
        self.entropy_seed = native.hash_text(self.entropy_seed + block_hash)

    def set_epoch(self, epoch: int):
        self.epoch = epoch

    def get_seed(self) -> str:
        return self.entropy_seed

    def _hash_int(self, *parts: object) -> int:
        payload = "|".join(str(part) for part in (self.entropy_seed, self.epoch, *parts))
        return int(native.hash_text(payload), 16)

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
        return native.validator_selection_proposer(
            self.entropy_seed,
            self.epoch,
            slot,
            [(str(addr), int(stake)) for addr, stake in validators.items()],
        )

    def select_proposer_weighted(self, validators: Dict[str, int], slot: int) -> Optional[str]:
        """
        Deterministic stake-weighted proposer selection.
        Higher stake expands the validator's interval in the canonical stake range.
        """
        return native.validator_selection_proposer_weighted(
            self.entropy_seed,
            self.epoch,
            slot,
            [(str(addr), int(stake)) for addr, stake in validators.items()],
        )

    def shuffle_validators(self, validators: Dict[str, int]) -> Dict[str, int]:
        """
        Epoch-based deterministic validator shuffling.
        Uses hash ranking instead of Python's process-local RNG implementation.
        """
        shuffled = native.validator_selection_shuffle(
            self.entropy_seed,
            self.epoch,
            [(str(addr), int(stake)) for addr, stake in validators.items()],
        )
        return dict(shuffled)

    def get_committee(self, validators: Dict[str, int], committee_size: int) -> List[str]:
        """
        Select deterministic hash-ranked committee for attestation aggregation.
        """
        return native.validator_selection_committee(
            self.entropy_seed,
            self.epoch,
            [(str(addr), int(stake)) for addr, stake in validators.items()],
            committee_size,
        )

    def get_stats(self) -> dict:
        return {
            "epoch": self.epoch,
            "seed": self.entropy_seed[:16] + "...",
            "seed_length": len(self.entropy_seed)
        }
