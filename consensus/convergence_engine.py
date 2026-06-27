# -*- coding: utf-8 -*-
"""Consensus convergence helpers for legacy v52 tests."""
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from consensus.validator_registry import ValidatorRegistry


def finality_threshold(total_validators: int) -> int:
    return (2 * total_validators + 2) // 3


def is_supermajority(votes: int, total_validators: int) -> bool:
    return votes >= finality_threshold(total_validators)


@dataclass
class BlockWeight:
    total_weight: float = 0.0


class ConvergenceEngine:
    def __init__(self, node: Any):
        self.node = node

    def calculate_block_weight(self, block: Dict, registry: ValidatorRegistry) -> BlockWeight:
        proposer = block.get("proposer", "")
        validator = registry.get_validator(proposer)
        weight = validator.get_score() if validator else 1.0
        return BlockWeight(total_weight=max(1.0, float(weight)))

    def calculate_chain_weight(self, blocks: List[Dict], registry: ValidatorRegistry) -> float:
        return sum(self.calculate_block_weight(block, registry).total_weight for block in blocks)

    def check_finality(self, block: Dict, votes: List[Dict], total_validators: int) -> bool:
        return len(votes) >= finality_threshold(total_validators)

    def choose_canonical_chain(self, chains: Dict[str, List[Dict]], registry: ValidatorRegistry) -> Optional[str]:
        best_name = None
        best_weight = -1.0
        for name, blocks in chains.items():
            weight = self.calculate_chain_weight(blocks, registry)
            if weight > best_weight:
                best_weight = weight
                best_name = name
        return best_name

    def maybe_reorganize(self, new_chain: List[Dict], current_chain: List[Dict], registry: ValidatorRegistry) -> bool:
        return self.calculate_chain_weight(new_chain, registry) > self.calculate_chain_weight(current_chain, registry)

    def process_attestation(self, attestation: Dict, registry: ValidatorRegistry) -> bool:
        validator = registry.get_validator(attestation.get("validator", ""))
        if validator:
            validator.record_vote()
            return True
        return False
