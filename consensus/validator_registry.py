# consensus/validator_registry.py
"""
Validator Registry with scoring, slashing, and reputation
"""

import time
import threading
from typing import Dict, List, Optional


class ValidatorState:
    """State of a single validator"""
    
    def __init__(self, address: str, stake: int = 0):
        self.address = address
        self.stake = stake
        self.reputation = 1.0  # Start with neutral reputation
        self.missed_blocks = 0
        self.slashed = False
        self.slash_count = 0
        self.produced_blocks = 0
        self.voted_blocks = 0
        self.last_active = time.time()
    
    def get_score(self) -> float:
        """Calculate validator score"""
        if self.slashed:
            return 0
        base_score = self.stake * self.reputation
        penalty = self.missed_blocks * 0.1
        return max(0, base_score - penalty)
    
    def slash(self):
        """Slash validator (reduce reputation)"""
        self.reputation *= 0.5
        self.slash_count += 1
        self.slashed = True
        print(f"⚠️ Validator {self.address[:16]}... SLASHED! Reputation: {self.reputation}")
    
    def record_missed_block(self):
        """Record a missed block"""
        self.missed_blocks += 1
        if self.missed_blocks > 10:
            self.slash()
    
    def record_produced_block(self):
        """Record a produced block"""
        self.produced_blocks += 1
        self.missed_blocks = max(0, self.missed_blocks - 1)  # Reduce penalty
    
    def record_vote(self):
        """Record a vote"""
        self.voted_blocks += 1
        self.last_active = time.time()
    
    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "stake": self.stake,
            "reputation": self.reputation,
            "score": self.get_score(),
            "missed_blocks": self.missed_blocks,
            "slashed": self.slashed,
            "produced_blocks": self.produced_blocks,
            "voted_blocks": self.voted_blocks
        }


class ValidatorRegistry:
    """Manages all validators and their scores"""
    
    def __init__(self):
        self.validators: Dict[str, ValidatorState] = {}
        self.lock = threading.RLock()
    
    def register_validator(self, address: str, stake: int) -> bool:
        """Register a new validator"""
        with self.lock:
            if address in self.validators:
                return False
            self.validators[address] = ValidatorState(address, stake)
            print(f"✅ Validator registered: {address[:16]}... stake={stake}")
            return True
    
    def get_validator(self, address: str) -> Optional[ValidatorState]:
        with self.lock:
            return self.validators.get(address)
    
    def get_all_validators(self) -> List[ValidatorState]:
        with self.lock:
            return list(self.validators.values())
    
    def get_total_stake(self) -> int:
        with self.lock:
            return sum(v.stake for v in self.validators.values())
    
    def record_produced_block(self, address: str):
        with self.lock:
            v = self.validators.get(address)
            if v:
                v.record_produced_block()
    
    def record_missed_block(self, address: str):
        with self.lock:
            v = self.validators.get(address)
            if v:
                v.record_missed_block()
    
    def record_vote(self, address: str):
        with self.lock:
            v = self.validators.get(address)
            if v:
                v.record_vote()
    
    def slash_validator(self, address: str):
        with self.lock:
            v = self.validators.get(address)
            if v:
                v.slash()
    
    def get_top_validators(self, limit: int = 21) -> List[ValidatorState]:
        """Get top validators by score"""
        with self.lock:
            sorted_validators = sorted(
                self.validators.values(),
                key=lambda v: v.get_score(),
                reverse=True
            )
            return sorted_validators[:limit]
    
    def get_stats(self) -> dict:
        with self.lock:
            if not self.validators:
                return {"total_validators": 0, "total_stake": 0, "active": 0}
            
            active = sum(1 for v in self.validators.values() if not v.slashed)
            return {
                "total_validators": len(self.validators),
                "total_stake": sum(v.stake for v in self.validators.values()),
                "active_validators": active,
                "slashed_validators": len(self.validators) - active
            }
