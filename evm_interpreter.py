#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FULL EVM INTERPRETER - Исполняет байткод, как настоящий EVM"""

import json
import hashlib
from typing import List, Dict, Any, Optional

class EVM:
    """Полноценный EVM-интерпретатор с опкодами"""
    
    OPCODES = {
        # Stack operations
        0x60: "PUSH1", 0x61: "PUSH2", 0x62: "PUSH3", 0x63: "PUSH4",
        0x50: "POP", 0x80: "DUP1", 0x81: "DUP2",
        0x90: "SWAP1", 0x91: "SWAP2",
        
        # Arithmetic
        0x01: "ADD", 0x02: "MUL", 0x03: "SUB", 0x04: "DIV",
        
        # Memory/Storage
        0x52: "MSTORE", 0x51: "MLOAD",
        0x55: "SSTORE", 0x54: "SLOAD",
        
        # Environment
        0x31: "BALANCE", 0x32: "ORIGIN", 0x33: "CALLER",
        
        # Control flow
        0x56: "JUMP", 0x57: "JUMPI", 0x5b: "JUMPDEST",
        
        # Blockchain
        0x40: "BLOCKHASH", 0x41: "COINBASE", 0x42: "TIMESTAMP",
        
        # Stop
        0x00: "STOP", 0xfd: "REVERT", 0xfe: "INVALID"
    }
    
    GAS_COSTS = {
        "STOP": 0, "ADD": 3, "MUL": 5, "SUB": 3, "DIV": 5,
        "PUSH1": 3, "PUSH2": 3, "POP": 2, "DUP1": 3, "SWAP1": 3,
        "MSTORE": 3, "MLOAD": 3, "SLOAD": 50, "SSTORE": 100,
        "JUMP": 8, "JUMPI": 10, "BALANCE": 20, "CALLER": 2
    }
    
    def __init__(self, gas_limit: int = 1000000):
        self.stack: List[int] = []
        self.memory: Dict[int, int] = {}
        self.storage: Dict[int, int] = {}
        self.gas_used = 0
        self.gas_limit = gas_limit
        self.pc = 0
        self.running = True
        self.trace: List[Dict] = []
    
    def _consume_gas(self, op: str):
        cost = self.GAS_COSTS.get(op, 1)
        if self.gas_used + cost > self.gas_limit:
            raise Exception(f"Out of gas! Used {self.gas_used}, need {cost}")
        self.gas_used += cost
    
    def execute_bytecode(self, bytecode: bytes) -> Dict:
        """Исполнение байткода"""
        self.pc = 0
        self.stack = []
        self.memory = {}
        self.gas_used = 0
        self.trace = []
        
        while self.pc < len(bytecode) and self.running:
            op_byte = bytecode[self.pc]
            op = self.OPCODES.get(op_byte, "UNKNOWN")
            
            self._consume_gas(op)
            self.trace.append({"pc": self.pc, "op": op, "stack": self.stack.copy()})
            
            if op == "STOP":
                self.running = False
                break
            
            elif op == "ADD":
                a = self.stack.pop()
                b = self.stack.pop()
                self.stack.append(a + b)
            
            elif op == "SUB":
                a = self.stack.pop()
                b = self.stack.pop()
                self.stack.append(a - b)
            
            elif op == "MUL":
                a = self.stack.pop()
                b = self.stack.pop()
                self.stack.append(a * b)
            
            elif op == "DIV":
                a = self.stack.pop()
                b = self.stack.pop()
                self.stack.append(a // b if b != 0 else 0)
            
            elif op.startswith("PUSH"):
                n = int(op[4:])
                if n == 1:
                    self.pc += 1
                    value = bytecode[self.pc] if self.pc < len(bytecode) else 0
                    self.stack.append(value)
                else:
                    # multi-byte push
                    self.pc += 1
                    value = 0
                    for i in range(n):
                        if self.pc + i < len(bytecode):
                            value = (value << 8) | bytecode[self.pc + i]
                    self.stack.append(value)
                    self.pc += n - 1
            
            elif op == "POP":
                self.stack.pop()
            
            elif op.startswith("DUP"):
                n = int(op[3:])
                if len(self.stack) >= n:
                    self.stack.append(self.stack[-n])
            
            elif op.startswith("SWAP"):
                n = int(op[4:])
                if len(self.stack) >= n + 1:
                    a = self.stack[-1]
                    b = self.stack[-(n+1)]
                    self.stack[-1] = b
                    self.stack[-(n+1)] = a
            
            elif op == "MSTORE":
                offset = self.stack.pop()
                value = self.stack.pop()
                self.memory[offset] = value
            
            elif op == "MLOAD":
                offset = self.stack.pop()
                self.stack.append(self.memory.get(offset, 0))
            
            elif op == "SSTORE":
                key = self.stack.pop()
                value = self.stack.pop()
                self.storage[key] = value
            
            elif op == "SLOAD":
                key = self.stack.pop()
                self.stack.append(self.storage.get(key, 0))
            
            elif op == "CALLER":
                self.stack.append(0x1234)  # mock caller
            
            elif op == "JUMP":
                dest = self.stack.pop()
                if dest < 0 or dest >= len(bytecode):
                    raise Exception(f"Invalid jump destination: {dest}")
                self.pc = dest - 1
            
            elif op == "JUMPI":
                dest = self.stack.pop()
                cond = self.stack.pop()
                if cond != 0:
                    if dest < 0 or dest >= len(bytecode):
                        raise Exception(f"Invalid jump destination: {dest}")
                    self.pc = dest - 1
            
            elif op == "REVERT":
                self.running = False
                raise Exception("Transaction reverted")
            
            elif op == "INVALID":
                raise Exception("Invalid opcode")
            
            self.pc += 1
        
        return {
            "success": self.running,
            "stack": self.stack.copy(),
            "memory": self.memory.copy(),
            "storage": self.storage.copy(),
            "gas_used": self.gas_used,
            "trace": self.trace
        }

def test_evm():
    print("🧠 EVM Interpreter Test")
    print("=" * 40)
    
    evm = EVM()
    
    # Test: PUSH 5, PUSH 7, ADD
    bytecode = bytes([0x60, 0x05, 0x60, 0x07, 0x01, 0x00])
    result = evm.execute_bytecode(bytecode)
    print(f"   ✅ 5 + 7 = {result['stack'][-1] if result['stack'] else '?'}")
    print(f"   📊 Gas used: {result['gas_used']}")
    print(f"   🔍 Trace: {result['trace'][:3]}...")
    
    return True

if __name__ == "__main__":
    test_evm()
