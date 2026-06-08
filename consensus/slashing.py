# consensus/slashing.py - Complete slashing engine
from typing import Dict, Set, Optional, List
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict

@dataclass
class SlashEvent:
    validator: str
    reason: str
    epoch: int
    timestamp: datetime
    penalty: int

class SlashingEngine:
    """Validator slashing mechanism"""
    
    PENALTIES = {
        "double_vote": 100,
        "double_proposal": 200,
        "offline": 10,
        "invalid_proposal": 50,
        "surround_vote": 75
    }
    
    def __init__(self):
        self.votes: Dict[str, Dict[int, str]] = {}
        self.proposals: Dict[int, Set[str]] = defaultdict(set)
        self.slashed: Set[str] = set()
        self.events: List[SlashEvent] = []
        self.missed_attestations: Dict[str, int] = defaultdict(int)
        
    def record_vote(self, validator: str, epoch: int, block_hash: str) -> bool:
        """Record validator vote, check for double voting"""
        if validator in self.slashed:
            return False
        
        if validator not in self.votes:
            self.votes[validator] = {}
        
        if epoch in self.votes[validator]:
            if self.votes[validator][epoch] != block_hash:
                self._slash(validator, "double_vote", epoch)
                return False
        
        self.votes[validator][epoch] = block_hash
        return True
    
    def record_proposal(self, validator: str, height: int, block_hash: str) -> bool:
        """Record block proposal, check for double proposal"""
        if validator in self.slashed:
            return False
        
        if height in self.proposals and validator in self.proposals[height]:
            self._slash(validator, "double_proposal", height // 32)
            return False
        
        self.proposals[height].add(validator)
        return True
    
    def record_missed_attestation(self, validator: str):
        """Record missed attestation"""
        if validator not in self.slashed:
            self.missed_attestations[validator] += 1
            
            if self.missed_attestations[validator] > 50:
                self._slash(validator, "offline", 0)
    
    def report_invalid_proposal(self, validator: str, height: int):
        """Report invalid block proposal"""
        self._slash(validator, "invalid_proposal", height // 32)
    
    def _slash(self, validator: str, reason: str, epoch: int):
        """Slash validator"""
        if validator in self.slashed:
            return
        
        penalty = self.PENALTIES.get(reason, 50)
        self.slashed.add(validator)
        
        event = SlashEvent(
            validator=validator,
            reason=reason,
            epoch=epoch,
            timestamp=datetime.now(),
            penalty=penalty
        )
        self.events.append(event)
        
        print(f"   ⚡ SLASH: {validator[:16]}... | {reason} | penalty={penalty}")
    
    def is_slashed(self, validator: str) -> bool:
        return validator in self.slashed
    
    def get_slashed_count(self) -> int:
        return len(self.slashed)
    
    def get_events(self) -> List[SlashEvent]:
        return self.events.copy()
    
    def clear_epoch(self, epoch: int):
        """Clear old epoch data"""
        for validator in list(self.votes.keys()):
            if epoch in self.votes[validator]:
                del self.votes[validator][epoch]
    
    def get_stats(self) -> dict:
        return {
            "slashed_count": len(self.slashed),
            "total_events": len(self.events),
            "by_reason": {reason: len([e for e in self.events if e.reason == reason]) 
                         for reason in self.PENALTIES}
        }
