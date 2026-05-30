# consensus/convergence_engine.py
"""
Consensus Convergence Engine
Chain selection based on validator scores and finality
Byzantine fault tolerant with 2/3+ supermajority
"""

import time
from typing import List, Optional, Dict
from dataclasses import dataclass


def finality_threshold(total_validators: int) -> int:
    """
    Calculate required votes for 2/3+ supermajority.
    Uses integer arithmetic to avoid float precision issues.
    
    Formula: ceil(2/3 * total) = (2 * total + 2) // 3
    
    Examples:
    - 3 validators: (6+2)//3 = 2 -> need 2 votes
    - 4 validators: (8+2)//3 = 3 -> need 3 votes
    - 6 validators: (12+2)//3 = 4 -> need 4 votes
    - 7 validators: (14+2)//3 = 5 -> need 5 votes
    """
    return (2 * total_validators + 2) // 3


def is_supermajority(votes: int, total_validators: int) -> bool:
    """Check if votes reach Byzantine quorum (2/3+ supermajority)"""
    return votes >= finality_threshold(total_validators)


@dataclass
class BlockWeight:
    """Weight of a block in consensus"""
    block_hash: str
    validator_score: float
    finality_bonus: int
    timestamp: float
    total_weight: float = 0
    
    def calculate(self):
        self.total_weight = self.validator_score + self.finality_bonus


class ConvergenceEngine:
    """
    Determines canonical chain based on:
    - Validator scores (stake + reputation)
    - Finality status (2/3+ supermajority)
    - Chain weight (sum of block weights)
    """
    
    def __init__(self, node):
        self.node = node
        self.finalized_blocks: Dict[str, bool] = {}
    
    # ==================== WEIGHT CALCULATION ====================
    
    def calculate_block_weight(self, block: dict, validator_registry) -> BlockWeight:
        """Calculate weight of a single block"""
        validator_addr = block.get("proposer", block.get("validator", ""))
        validator = validator_registry.get_validator(validator_addr)
        
        if validator:
            validator_score = validator.get_score()
        else:
            validator_score = 0
        
        finality_bonus = 100 if self.is_finalized(block) else 0
        
        weight = BlockWeight(
            block_hash=block.get("hash", ""),
            validator_score=validator_score,
            finality_bonus=finality_bonus,
            timestamp=block.get("timestamp", time.time())
        )
        weight.calculate()
        return weight
    
    def calculate_chain_weight(self, chain_blocks: List[dict], validator_registry) -> float:
        """Calculate total weight of a chain"""
        total_weight = 0
        for block in chain_blocks:
            weight = self.calculate_block_weight(block, validator_registry)
            total_weight += weight.total_weight
        return total_weight
    
    # ==================== FINALITY ====================
    
    def check_finality(self, block: dict, votes: List[dict], total_validators: int) -> bool:
        """
        Check if block has reached finality (2/3+ supermajority)
        Uses Byzantine quorum: need ceil(2/3 * total_validators)
        """
        if not votes:
            return False
        
        total_votes = len(votes)
        # Correct integer arithmetic for supermajority
        threshold = finality_threshold(total_validators)
        
        is_final = total_votes >= threshold
        if is_final:
            self.finalized_blocks[block.get("hash", "")] = True
            print(f"🔒 Block {block.get('hash', '')[:16]}... FINALIZED! ({total_votes}/{total_validators} votes, threshold={threshold})")
        
        return is_final
    
    def is_finalized(self, block: dict) -> bool:
        """Check if block is marked as finalized"""
        return self.finalized_blocks.get(block.get("hash", ""), False)
    
    def mark_finalized(self, block_hash: str):
        """Manually mark block as finalized"""
        self.finalized_blocks[block_hash] = True
    
    # ==================== CHAIN SELECTION ====================
    
    def choose_canonical_chain(self, chains: Dict[str, List[dict]], validator_registry) -> Optional[List[dict]]:
        """
        Choose the best chain based on weight
        """
        best_chain = None
        best_weight = -1
        
        for chain_id, chain_blocks in chains.items():
            weight = self.calculate_chain_weight(chain_blocks, validator_registry)
            if weight > best_weight:
                best_weight = weight
                best_chain = chain_blocks
        
        if best_chain:
            print(f"[CONSENSUS] Canonical chain selected: weight={best_weight:.2f}, length={len(best_chain)}")
        
        return best_chain
    
    # ==================== REORG HANDLING ====================
    
    def maybe_reorganize(self, new_chain: List[dict], current_chain: List[dict], validator_registry) -> bool:
        """
        Check if we should reorganize to new chain
        """
        current_weight = self.calculate_chain_weight(current_chain, validator_registry)
        new_weight = self.calculate_chain_weight(new_chain, validator_registry)
        
        if new_weight > current_weight:
            print(f"[CONSENSUS] Reorg triggered!")
            print(f"  Current weight: {current_weight:.2f}")
            print(f"  New weight: {new_weight:.2f}")
            return True
        
        return False
    
    def reorganize(self, new_chain: List[dict]):
        """Execute chain reorganization"""
        if hasattr(self.node, 'chain'):
            self.node.chain.replace_with(new_chain)
            print(f"[CONSENSUS] Chain replaced. New height: {len(new_chain)}")
    
    # ==================== VOTE PROCESSING ====================
    
    def process_attestation(self, attestation: dict, validator_registry) -> bool:
        """
        Process validator attestation (vote)
        """
        validator_addr = attestation.get("validator")
        block_hash = attestation.get("target_hash")
        
        validator = validator_registry.get_validator(validator_addr)
        if validator and not validator.slashed:
            validator.record_vote()
            return True
        
        return False
    
    # ==================== UTILITIES ====================
    
    def get_stats(self) -> dict:
        return {
            "finalized_blocks": len(self.finalized_blocks),
            "finality_threshold": "2/3 (Byzantine quorum)"
        }
