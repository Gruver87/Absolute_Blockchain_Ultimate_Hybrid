#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CONSENSUS ENGINE - PoS валидаторы и аттестации"""

import random
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class Validator:
    address: str
    stake: float
    is_active: bool = True
    attestations: int = 0
    blocks_proposed: int = 0

class ConsensusEngine:
    """PoS консенсус с валидаторами и аттестациями"""
    
    SLOTS_PER_EPOCH = 32
    SECONDS_PER_SLOT = 12
    
    def __init__(self):
        self.validators: Dict[str, Validator] = {}
        self.current_epoch = 0
        self.current_slot = 0
        self.attestations: Dict[int, List[str]] = defaultdict(list)
        self.finalized_checkpoints: List[int] = []
    
    def add_validator(self, address: str, stake: float) -> bool:
        if address in self.validators:
            return False
        self.validators[address] = Validator(address, stake)
        return True
    
    def get_total_stake(self) -> float:
        return sum(v.stake for v in self.validators.values() if v.is_active)
    
    def select_proposer(self) -> Optional[Validator]:
        """Выбор proposer для текущего слота (а-ля RANDAO)"""
        total_stake = self.get_total_stake()
        if total_stake == 0:
            return None
        
        # Симуляция RANDAO
        random.seed(self.current_slot + self.current_epoch * 1000)
        pick = random.uniform(0, total_stake)
        
        current = 0
        for val in self.validators.values():
            if not val.is_active:
                continue
            current += val.stake
            if current >= pick:
                return val
        return None
    
    def get_committee(self, slot: int) -> List[Validator]:
        """Получение комитета аттестаторов для слота"""
        committee_size = max(1, len(self.validators) // 32)
        random.seed(slot)
        validators_list = [v for v in self.validators.values() if v.is_active]
        if not validators_list:
            return []
        return random.sample(validators_list, min(committee_size, len(validators_list)))
    
    def attest(self, validator_addr: str, slot: int, block_hash: str) -> bool:
        """Аттестация блока валидатором"""
        if validator_addr not in self.validators:
            return False
        
        validator = self.validators[validator_addr]
        if not validator.is_active:
            return False
        
        validator.attestations += 1
        self.attestations[slot].append(validator_addr)
        return True
    
    def advance_slot(self) -> int:
        """Переход к следующему слоту"""
        self.current_slot += 1
        if self.current_slot % self.SLOTS_PER_EPOCH == 0:
            self.current_epoch += 1
            self._finalize_checkpoint()
        return self.current_slot
    
    def _finalize_checkpoint(self):
        """Финализация чекпоинта (2/3+ аттестаций)"""
        total = len(self.validators)
        if total == 0:
            return
        
        for slot, attestors in self.attestations.items():
            if len(attestors) > total * 2 / 3:
                self.finalized_checkpoints.append(slot)
                print(f"   🔒 Finalized checkpoint at slot {slot}")
    
    def get_stats(self) -> Dict:
        return {
            "epoch": self.current_epoch,
            "slot": self.current_slot,
            "validators": len(self.validators),
            "total_stake": self.get_total_stake(),
            "finalized_checkpoints": len(self.finalized_checkpoints)
        }

def test_consensus():
    print("⛓️ Consensus Engine (PoS)")
    print("=" * 40)
    
    engine = ConsensusEngine()
    
    # Добавляем валидаторов
    for i in range(10):
        engine.add_validator(f"0xvalidator_{i}", random.uniform(100, 1000))
    
    print(f"   👥 Validators: {len(engine.validators)}")
    print(f"   💰 Total stake: {engine.get_total_stake():.0f}")
    
    # Симуляция 30 слотов
    for slot in range(30):
        proposer = engine.select_proposer()
        committee = engine.get_committee(slot)
        
        if proposer:
            engine.attest(proposer.address, slot, f"block_{slot}")
        
        for attester in committee[:3]:  # несколько аттестаций
            engine.attest(attester.address, slot, f"block_{slot}")
        
        engine.advance_slot()
    
    stats = engine.get_stats()
    print(f"   📊 Stats: epoch {stats['epoch']}, slot {stats['slot']}")
    print(f"   🔒 Finalized: {stats['finalized_checkpoints']} checkpoints")
    
    return True

if __name__ == "__main__":
    test_consensus()
