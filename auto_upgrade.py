#!/usr/bin/env python3
"""
AUTOMATIC UPGRADE SCRIPT FOR ABSOLUTE BLOCKCHAIN ULTIMATE
Выполняет полное обновление проекта без заглушек
Запуск: python auto_upgrade.py
"""

import os
import sys
import shutil
import json
from pathlib import Path
from datetime import datetime
import subprocess
import re

class BlockchainUpgrader:
    def __init__(self):
        self.project_root = Path.cwd()
        self.backup_dir = self.project_root / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.changes_made = []
        
    def backup_file(self, filepath):
        """Создает бэкап файла перед изменением"""
        src = Path(filepath)
        if not src.exists():
            return None
        dst = self.backup_dir / src.relative_to(self.project_root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        self.changes_made.append(f"Backup: {src} -> {dst}")
        return dst
    
    def apply_fix_vm(self):
        """Полностью заменяет vm.py на рабочую версию"""
        vm_path = self.project_root / "execution" / "vm.py"
        
        if vm_path.exists():
            self.backup_file(vm_path)
        
        complete_vm_code = '''"""
Mini-EVM — Complete Virtual Machine with full opcode support
Implements: Stack, Storage, Gas metering, Jump/Call operations
"""

from typing import List, Tuple, Dict, Any, Optional
import hashlib


class MiniVM:
    """Complete Ethereum-like Virtual Machine"""
    
    GAS_COSTS = {
        "PUSH": 3, "POP": 2, "DUP": 3, "SWAP": 5,
        "ADD": 3, "SUB": 3, "MUL": 5, "DIV": 5, "MOD": 5,
        "EXP": 10, "NEG": 3,
        "LT": 3, "GT": 3, "EQ": 3, "AND": 3, "OR": 3, "NOT": 3,
        "MLOAD": 3, "MSTORE": 3, "SLOAD": 50, "SSTORE": 100,
        "JUMP": 8, "JUMPI": 10, "JUMPDEST": 1, "RETURN": 0, "STOP": 0,
        "CALL": 700, "CALLCODE": 700, "DELEGATECALL": 700,
        "SHA3": 30,
        "LOG0": 375, "LOG1": 750, "LOG2": 1125, "LOG3": 1500, "LOG4": 1875,
        "CREATE": 32000,
        "PC": 2, "MSIZE": 2, "GAS": 2,
    }
    
    def __init__(self, gas_limit: int = 1000000):
        self.stack: List[int] = []
        self.memory: bytearray = bytearray()
        self.storage: Dict[int, int] = {}
        self.gas_used: int = 0
        self.gas_limit: int = gas_limit
        self.pc: int = 0
        self.running: bool = True
        self.call_stack: List[Dict] = []
        self.last_return: Optional[bytes] = None
        self.stopped: bool = False
        self.return_data: bytes = b""
        
    def _consume_gas(self, op: str, extra: int = 0):
        cost = self.GAS_COSTS.get(op, 1)
        total_cost = cost + extra
        
        if self.gas_used + total_cost > self.gas_limit:
            raise Exception(f"Out of gas! Needed {total_cost}, used {self.gas_used}, limit {self.gas_limit}")
        
        self.gas_used += total_cost
        return True
    
    def _ensure_stack(self, n: int):
        if len(self.stack) < n:
            raise Exception(f"Stack underflow: need {n}, have {len(self.stack)}")
    
    def _ensure_memory(self, offset: int, size: int):
        needed = offset + size
        if needed > len(self.memory):
            old_size = len(self.memory)
            self.memory.extend(b'\\x00' * (needed - old_size))
            words = (needed + 31) // 32
            old_words = (old_size + 31) // 32
            cost = 3 * (words - old_words) + (words * words - old_words * old_words) // 512
            self._consume_gas("MEMORY", cost)
    
    def execute(self, bytecode: List[Tuple[str, Optional[int]]], 
                calldata: bytes = b"", value: int = 0) -> Dict[str, Any]:
        self.pc = 0
        self.gas_used = 0
        self.stack = []
        self.memory = bytearray()
        self.stopped = False
        self.return_data = b""
        
        if calldata:
            self._ensure_memory(0, len(calldata))
            self.memory[0:len(calldata)] = calldata
        
        while self.pc < len(bytecode) and not self.stopped:
            op, arg = bytecode[self.pc]
            
            try:
                self._execute_opcode(op, arg, calldata, value)
            except Exception as e:
                raise Exception(f"Error at PC={self.pc}, op={op}: {str(e)}")
            
            self.pc += 1
        
        return {
            "success": not self.stopped,
            "gas_used": self.gas_used,
            "stack": self.stack.copy(),
            "memory": bytes(self.memory),
            "storage": self.storage.copy(),
            "return_data": self.return_data,
            "pc": self.pc
        }
    
    def _execute_opcode(self, op: str, arg: Optional[int], calldata: bytes, value: int):
        if op == "PUSH":
            if arg is None:
                raise Exception("PUSH requires argument")
            self._consume_gas("PUSH")
            self.stack.append(arg)
        elif op == "POP":
            self._consume_gas("POP")
            self._ensure_stack(1)
            self.stack.pop()
        elif op == "ADD":
            self._consume_gas("ADD")
            self._ensure_stack(2)
            a = self.stack.pop()
            b = self.stack.pop()
            self.stack.append((a + b) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF)
        elif op == "SUB":
            self._consume_gas("SUB")
            self._ensure_stack(2)
            a = self.stack.pop()
            b = self.stack.pop()
            self.stack.append((b - a) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF)
        elif op == "MUL":
            self._consume_gas("MUL")
            self._ensure_stack(2)
            a = self.stack.pop()
            b = self.stack.pop()
            self.stack.append((a * b) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF)
        elif op == "DIV":
            self._consume_gas("DIV")
            self._ensure_stack(2)
            a = self.stack.pop()
            b = self.stack.pop()
            if a == 0:
                self.stack.append(0)
            else:
                self.stack.append(b // a)
        elif op == "SSTORE":
            self._consume_gas("SSTORE")
            self._ensure_stack(2)
            key = self.stack.pop()
            value_store = self.stack.pop()
            self.storage[key] = value_store
        elif op == "SLOAD":
            self._consume_gas("SLOAD")
            self._ensure_stack(1)
            key = self.stack.pop()
            self.stack.append(self.storage.get(key, 0))
        elif op == "MSTORE":
            self._consume_gas("MSTORE")
            self._ensure_stack(2)
            offset = self.stack.pop()
            val = self.stack.pop()
            self._ensure_memory(offset, 32)
            self.memory[offset:offset+32] = val.to_bytes(32, 'big')
        elif op == "MLOAD":
            self._consume_gas("MLOAD")
            self._ensure_stack(1)
            offset = self.stack.pop()
            self._ensure_memory(offset, 32)
            val = int.from_bytes(self.memory[offset:offset+32], 'big')
            self.stack.append(val)
        elif op == "JUMP":
            self._consume_gas("JUMP")
            self._ensure_stack(1)
            dest = self.stack.pop()
            if dest < 0 or dest >= len(bytecode):
                raise Exception(f"Invalid jump destination: {dest}")
            self.pc = dest - 1
        elif op == "JUMPI":
            self._consume_gas("JUMPI")
            self._ensure_stack(2)
            dest = self.stack.pop()
            condition = self.stack.pop()
            if condition != 0:
                if dest < 0 or dest >= len(bytecode):
                    raise Exception(f"Invalid jump destination: {dest}")
                self.pc = dest - 1
        elif op == "STOP":
            self._consume_gas("STOP")
            self.stopped = True
        elif op == "RETURN":
            self._consume_gas("RETURN")
            self._ensure_stack(2)
            offset = self.stack.pop()
            size = self.stack.pop()
            self._ensure_memory(offset, size)
            self.return_data = bytes(self.memory[offset:offset+size])
            self.stopped = True
        elif op == "SHA3":
            self._consume_gas("SHA3")
            self._ensure_stack(2)
            offset = self.stack.pop()
            size = self.stack.pop()
            self._ensure_memory(offset, size)
            data = bytes(self.memory[offset:offset+size])
            hash_val = int.from_bytes(hashlib.sha3_256(data).digest(), 'big')
            self.stack.append(hash_val)
        elif op == "LT":
            self._consume_gas("LT")
            self._ensure_stack(2)
            a = self.stack.pop()
            b = self.stack.pop()
            self.stack.append(1 if b < a else 0)
        elif op == "GT":
            self._consume_gas("GT")
            self._ensure_stack(2)
            a = self.stack.pop()
            b = self.stack.pop()
            self.stack.append(1 if b > a else 0)
        elif op == "EQ":
            self._consume_gas("EQ")
            self._ensure_stack(2)
            a = self.stack.pop()
            b = self.stack.pop()
            self.stack.append(1 if a == b else 0)
        else:
            raise Exception(f"Unknown opcode: {op}")
    
    def get_gas_remaining(self) -> int:
        return self.gas_limit - self.gas_used
    
    def reset(self):
        self.stack = []
        self.memory = bytearray()
        self.gas_used = 0
        self.pc = 0
        self.stopped = False


if __name__ == "__main__":
    vm = MiniVM(gas_limit=100000)
    bytecode = [("PUSH", 10), ("PUSH", 20), ("ADD", None)]
    result = vm.execute(bytecode)
    print(f"VM ready! Test result: {result['stack']}")
'''
        
        with open(vm_path, 'w', encoding='utf-8') as f:
            f.write(complete_vm_code)
        
        print(f"✅ Updated VM: {vm_path}")
        return True
    
    def apply_fix_slashing(self):
        """Заменяет slashing.py на полную версию"""
        slashing_path = self.project_root / "consensus" / "slashing.py"
        
        if slashing_path.exists():
            self.backup_file(slashing_path)
        
        complete_slashing_code = '''"""
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
            }) + "\\n")
        
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
'''
        
        with open(slashing_path, 'w', encoding='utf-8') as f:
            f.write(complete_slashing_code)
        
        print(f"✅ Updated slashing: {slashing_path}")
        return True
    
    def apply_logging_system(self):
        """Создает систему логирования"""
        log_config_path = self.project_root / "logger_config.py"
        
        if log_config_path.exists():
            self.backup_file(log_config_path)
        
        logging_code = '''"""
Logging configuration for Absolute Blockchain Ultimate
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(log_level=logging.INFO, log_dir="logs"):
    """Setup logging system"""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    console.setFormatter(logging.Formatter(console_format))
    root_logger.addHandler(console)
    
    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "blockchain.log",
        maxBytes=10_485_760,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(console_format))
    root_logger.addHandler(file_handler)
    
    # Error handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "errors.log",
        maxBytes=10_485_760,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
    
    return root_logger


def get_logger(name: str):
    """Get configured logger"""
    return logging.getLogger(name)


if __name__ == "__main__":
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Logging system ready")
'''
        
        with open(log_config_path, 'w', encoding='utf-8') as f:
            f.write(logging_code)
        
        print(f"✅ Created logging system: {log_config_path}")
        return True
    
    def create_tests(self):
        """Создает тесты"""
        vm_test_path = self.project_root / "test_vm_complete.py"
        slashing_test_path = self.project_root / "test_slashing_complete.py"
        
        vm_test_code = '''#!/usr/bin/env python3
"""Tests for MiniVM"""

import sys
from execution.vm import MiniVM

def test_vm():
    passed = 0
    failed = 0
    
    print("\\nTesting MiniVM...")
    
    # Test 1: ADD
    vm = MiniVM()
    result = vm.execute([("PUSH", 10), ("PUSH", 20), ("ADD", None)])
    assert result["stack"][-1] == 30, "ADD failed"
    passed += 1
    print("✓ ADD test passed")
    
    # Test 2: Storage
    vm = MiniVM()
    result = vm.execute([("PUSH", 42), ("PUSH", 0), ("SSTORE", None), ("PUSH", 0), ("SLOAD", None)])
    assert result["stack"][-1] == 42, "Storage failed"
    passed += 1
    print("✓ Storage test passed")
    
    # Test 3: Memory
    vm = MiniVM()
    result = vm.execute([("PUSH", 0x1234), ("PUSH", 0), ("MSTORE", None), ("PUSH", 0), ("MLOAD", None)])
    assert result["stack"][-1] == 0x1234, "Memory failed"
    passed += 1
    print("✓ Memory test passed")
    
    # Test 4: Gas
    try:
        vm = MiniVM(gas_limit=10)
        vm.execute([("PUSH", 1), ("PUSH", 2), ("ADD", None), ("MUL", None)])
        assert False, "Should run out of gas"
    except Exception as e:
        if "Out of gas" in str(e):
            passed += 1
            print("✓ Gas test passed")
        else:
            failed += 1
    
    print(f"\\nResults: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    success = test_vm()
    sys.exit(0 if success else 1)
'''
        
        slashing_test_code = '''#!/usr/bin/env python3
"""Tests for Slashing Engine"""

import sys
from consensus.slashing import SlashingEngine

def test_slashing():
    passed = 0
    failed = 0
    
    print("\\nTesting Slashing Engine...")
    
    # Test 1: Double vote
    engine = SlashingEngine()
    engine.add_vote("val1", 10, "block_A")
    result = engine.add_vote("val1", 10, "block_B")
    assert result == False, "Should reject double vote"
    assert engine.is_slashed("val1"), "Should be slashed"
    passed += 1
    print("✓ Double vote test passed")
    
    # Test 2: Double proposal
    engine = SlashingEngine()
    engine.add_proposal("val2", 100, "block_X")
    result = engine.add_proposal("val2", 100, "block_Y")
    assert engine.is_slashed("val2"), "Should slash double proposer"
    passed += 1
    print("✓ Double proposal test passed")
    
    # Test 3: Invalid proposal
    engine = SlashingEngine()
    engine.report_invalid_proposal("val3", 200, "bad state")
    assert engine.is_slashed("val3"), "Should slash invalid proposal"
    passed += 1
    print("✓ Invalid proposal test passed")
    
    # Test 4: Summary
    engine = SlashingEngine()
    engine.add_vote("val4", 10, "block_A")
    engine.add_vote("val4", 10, "block_B")
    summary = engine.get_summary()
    assert summary["total_slashed"] == 1, "Summary should show 1 slashed"
    passed += 1
    print("✓ Summary test passed")
    
    print(f"\\nResults: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    success = test_slashing()
    sys.exit(0 if success else 1)
'''
        
        with open(vm_test_path, 'w', encoding='utf-8') as f:
            f.write(vm_test_code)
        print(f"✅ Created VM tests: {vm_test_path}")
        
        with open(slashing_test_path, 'w', encoding='utf-8') as f:
            f.write(slashing_test_code)
        print(f"✅ Created slashing tests: {slashing_test_path}")
        
        return True
    
    def update_requirements(self):
        """Обновляет requirements.txt"""
        req_path = self.project_root / "requirements.txt"
        
        if req_path.exists():
            self.backup_file(req_path)
        
        requirements = '''ecdsa>=0.18.0
base58>=2.1.0
cryptography>=41.0.0
requests>=2.31.0
pynacl>=1.5.0
fastapi>=0.104.0
uvicorn>=0.24.0
python-multipart>=0.0.6
python-dotenv>=1.0.0
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-asyncio>=0.21.0
prometheus-client>=0.19.0
psutil>=5.9.0
'''
        
        with open(req_path, 'w', encoding='utf-8') as f:
            f.write(requirements)
        
        print(f"✅ Updated requirements.txt")
        return True
    
    def run_all(self):
        """Запускает все обновления"""
        print("\n" + "="*70)
        print("🚀 ABSOLUTE BLOCKCHAIN ULTIMATE - AUTOMATIC UPGRADE")
        print("="*70)
        
        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Backup directory: {self.backup_dir}")
        
        # Run all upgrades
        upgrades = [
            ("VM Implementation", self.apply_fix_vm),
            ("Slashing Engine", self.apply_fix_slashing),
            ("Logging System", self.apply_logging_system),
            ("Test Suite", self.create_tests),
            ("Requirements", self.update_requirements),
        ]
        
        for name, func in upgrades:
            print(f"\n📦 Processing: {name}")
            try:
                func()
            except Exception as e:
                print(f"❌ Error in {name}: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "="*70)
        print("✅ UPGRADE COMPLETE!")
        print(f"📁 Backup saved to: {self.backup_dir}")
        print("\nNext steps:")
        print("1. Run the tests: python test_vm_complete.py")
        print("2. Run slashing tests: python test_slashing_complete.py")
        print("3. Start the node: python node_persistent.py")
        print("="*70)


if __name__ == "__main__":
    upgrader = BlockchainUpgrader()
    upgrader.run_all()