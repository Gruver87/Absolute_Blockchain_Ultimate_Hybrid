"""
Slashing Engine — Complete validator punishment system
"""

from typing import Dict, Set, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import json
from pathlib import Path


@dataclass
class SlashingRecord:
    validator: str
    reason: str
    timestamp: datetime
    epoch: int
    amount_slashed: int
    evidence: Dict


class SlashingEngine:
    """Complete Slashing Engine"""
    
    PENALTIES = {
        "DOUBLE_VOTE": 0.10,
        "DOUBLE_PROPOSE": 0.20,
        "OFFLINE": 0.01,
        "INVALID_PROPOSAL": 0.05,
    }
    
    MAX_MISSED_ATTESTATIONS = 50
    
    def __init__(self, min_validator_stake: int = 1000):
        self.votes: Dict[str, Dict[int, str]] = {}
        self.proposals: Dict[int, Set[str]] = defaultdict(set)
        self.slashed: Set[str] = set()
        self.reasons: Dict[str, str] = {}
        self.records: Dict[str, List[SlashingRecord]] = defaultdict(list)
        self.attestations: Dict[str, Dict[int, bool]] = {}
        self.min_stake = min_validator_stake
        self.total_slashed_amount = 0
        
    def add_vote(self, validator: str, epoch: int, block: str) -> bool:
        if self.is_slashed(validator):
            return False
            
        if validator not in self.votes:
            self.votes[validator] = {}
            
        if epoch in self.votes[validator]:
            old_block = self.votes[validator][epoch]
            if old_block != block:
                self._slash(validator, "DOUBLE_VOTE", epoch, 
                           {"first": old_block, "second": block})
                return False
                
        self.votes[validator][epoch] = block
        return True
        
    def add_proposal(self, validator: str, height: int, block_hash: str) -> bool:
        if self.is_slashed(validator):
            return False
            
        if height in self.proposals and validator in self.proposals[height]:
            self._slash(validator, "DOUBLE_PROPOSE", 0, {"height": height})
            return False
            
        self.proposals[height].add(validator)
        return True
        
    def add_attestation(self, validator: str, epoch: int, attested: bool = True):
        if self.is_slashed(validator):
            return
            
        if validator not in self.attestations:
            self.attestations[validator] = {}
            
        self.attestations[validator][epoch] = attested
        self._check_offline_validator(validator)
        
    def _check_offline_validator(self, validator: str):
        if validator not in self.attestations:
            return
            
        recent = sorted(self.attestations[validator].keys(), reverse=True)
        if len(recent) < self.MAX_MISSED_ATTESTATIONS:
            return
            
        missed = 0
        for epoch in recent[:self.MAX_MISSED_ATTESTATIONS]:
            if not self.attestations[validator][epoch]:
                missed += 1
                
        if missed > self.MAX_MISSED_ATTESTATIONS * 0.7:
            self._slash(validator, "OFFLINE", recent[0], 
                       {"missed": missed, "total": self.MAX_MISSED_ATTESTATIONS})
        
    def report_invalid_proposal(self, validator: str, height: int, reason: str):
        if not self.is_slashed(validator):
            self._slash(validator, "INVALID_PROPOSAL", 0, 
                       {"height": height, "reason": reason})
        
    def _slash(self, validator: str, reason: str, epoch: int, evidence: Dict):
        if validator in self.slashed:
            return
            
        penalty = self.PENALTIES.get(reason, 0.05)
        amount = int(self.min_stake * penalty)
        
        record = SlashingRecord(
            validator=validator,
            reason=reason,
            timestamp=datetime.now(),
            epoch=epoch,
            amount_slashed=amount,
            evidence=evidence
        )
        
        self.slashed.add(validator)
        self.reasons[validator] = reason
        self.records[validator].append(record)
        self.total_slashed_amount += amount
        
        print(f"[SLASH] {validator[:16]}...: {reason} (amount={amount})")
        
        # Log to file
        log_path = Path("logs")
        log_path.mkdir(exist_ok=True)
        with open(log_path / "slashing.log", "a") as f:
            f.write(json.dumps({
                "ts": record.timestamp.isoformat(),
                "validator": validator,
                "reason": reason,
                "amount": amount
            }) + "\n")
        
    def is_slashed(self, validator: str) -> bool:
        return validator in self.slashed
        
    def get_slash_info(self, validator: str) -> Optional[str]:
        return self.reasons.get(validator)
        
    def get_slashed_validators(self) -> Set[str]:
        return self.slashed.copy()
        
    def get_summary(self) -> Dict:
        return {
            "total_slashed": len(self.slashed),
            "total_amount": self.total_slashed_amount,
            "reasons": {
                reason: len([r for recs in self.records.values() for r in recs if r.reason == reason])
                for reason in self.PENALTIES
            }
        }
        
    def clear_epoch(self, epoch: int):
        to_remove = []
        for val, epochs in self.votes.items():
            if epoch in epochs:
                del epochs[epoch]
            if not epochs:
                to_remove.append(val)
        for val in to_remove:
            del self.votes[val]
            
    def reset(self):
        self.votes.clear()
        self.proposals.clear()
        self.slashed.clear()
        self.reasons.clear()
        self.records.clear()
        self.attestations.clear()
        self.total_slashed_amount = 0


if __name__ == "__main__":
    engine = SlashingEngine()
    print("Slashing engine ready!")
