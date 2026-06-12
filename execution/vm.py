<<<<<<< HEAD
﻿# execution/vm.py - FULLY FIXED
from typing import List, Tuple, Dict, Any, Optional

class MiniVM:
    GAS_COSTS = {
        "PUSH": 2, "POP": 2, "ADD": 3, "SUB": 3, "MUL": 5, "DIV": 5,
        "STORE": 20, "LOAD": 20, "STOP": 0, "INC": 2, "DEC": 2,
        "EQ": 3, "LT": 3, "GT": 3, "JUMP": 1, "JUMPI": 1,
=======
﻿# execution/vm.py - FINAL VERSION WITH CLEAR SEMANTICS
from typing import List, Tuple, Dict, Any, Optional
import hashlib

class MiniVM:
    """VM with Ethereum-compatible semantics: PUSH key, PUSH value, SSTORE"""
    
    GAS_COSTS = {
        "PUSH": 2, "POP": 2, "ADD": 3, "SUB": 3, "MUL": 5, "DIV": 5,
        "SSTORE": 100, "SLOAD": 50, "STOP": 0, "RETURN": 0,
        "LT": 3, "GT": 3, "EQ": 3, "SHA3": 30,
>>>>>>> e1325e33910593a6992287e350ec884bed59f946
    }
    
    def __init__(self, gas_limit: int = 10000):
        self.stack: List[int] = []
        self.storage: Dict[int, int] = {}
<<<<<<< HEAD
        self.gas_used = 0
        self.gas_limit = gas_limit
        self.pc = 0
        self.running = True
    
    def _consume_gas(self, op: str):
        cost = self.GAS_COSTS.get(op, 1)
        if self.gas_used + cost > self.gas_limit:
            raise Exception(f"Out of gas! Used {self.gas_used}, need {cost}, limit {self.gas_limit}")
        self.gas_used += cost
    
    def execute(self, bytecode: List[Tuple[str, Optional[int]]]) -> Dict[str, Any]:
        self.pc = 0
        self.gas_used = 0
        self.stack = []
        self.storage = {}
        self.running = True
        
        while self.pc < len(bytecode) and self.running:
=======
        self.gas_used: int = 0
        self.gas_limit: int = gas_limit
        self.pc: int = 0
        self.stopped: bool = False
        
    def _consume_gas(self, op: str):
        cost = self.GAS_COSTS.get(op, 1)
        self.gas_used += cost
        if self.gas_used > self.gas_limit:
            raise Exception(f"Out of gas")
    
    def _ensure_stack(self, n: int):
        if len(self.stack) < n:
            raise Exception(f"Stack underflow")
    
    def execute(self, bytecode: List[Tuple[str, Optional[int]]]) -> Dict[str, Any]:
        # Reset execution state but KEEP storage
        self.stack = []
        self.gas_used = 0
        self.pc = 0
        self.stopped = False
        # CRITICAL: self.storage is NOT cleared
        
        while self.pc < len(bytecode) and not self.stopped:
>>>>>>> e1325e33910593a6992287e350ec884bed59f946
            op, arg = bytecode[self.pc]
            self._consume_gas(op)
            
            if op == "PUSH":
<<<<<<< HEAD
                if arg is None:
                    raise Exception("PUSH requires argument")
                self.stack.append(arg)
            elif op == "POP":
                self.stack.pop()
            elif op == "ADD":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a + b)
            elif op == "SUB":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)  # a - b = правильный порядок
            elif op == "MUL":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)
            elif op == "DIV":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a // b if b != 0 else 0)
            elif op == "STORE":
                key = self.stack.pop()
                value = self.stack.pop()
                self.storage[key] = value
            elif op == "LOAD":
                key = self.stack.pop()
                self.stack.append(self.storage.get(key, 0))
            elif op == "INC":
                if not self.stack:
                    self.stack.append(0)
                self.stack[-1] += 1
            elif op == "DEC":
                if not self.stack:
                    self.stack.append(0)
                self.stack[-1] -= 1
            elif op == "EQ":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a == b else 0)
            elif op == "LT":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a < b else 0)
            elif op == "GT":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a > b else 0)
            elif op == "JUMP":
                dest = self.stack.pop()
                if dest < 0 or dest >= len(bytecode):
                    raise Exception(f"Invalid jump destination: {dest}")
                self.pc = dest
                continue
            elif op == "JUMPI":
                dest = self.stack.pop()
                cond = self.stack.pop()
                if cond != 0:
                    if dest < 0 or dest >= len(bytecode):
                        raise Exception(f"Invalid jump destination: {dest}")
                    self.pc = dest
                    continue
            elif op == "STOP":
                self.running = False
                break
            else:
                raise Exception(f"Unknown opcode: {op}")
=======
                self.stack.append(arg)
            
            elif op == "POP":
                self._ensure_stack(1)
                self.stack.pop()
            
            elif op == "ADD":
                self._ensure_stack(2)
                self.stack.append(self.stack.pop() + self.stack.pop())
            
            elif op == "SUB":
                self._ensure_stack(2)
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(a - b)
            
            elif op == "MUL":
                self._ensure_stack(2)
                self.stack.append(self.stack.pop() * self.stack.pop())
            
            elif op == "DIV":
                self._ensure_stack(2)
                b, a = self.stack.pop(), self.stack.pop()
                self.stack.append(0 if b == 0 else a // b)
            
            elif op == "SSTORE":
                self._ensure_stack(2)
                # SEMANTICS: PUSH key, PUSH value, SSTORE
                # Stack after PUSHes: [key, value]
                # So pop() gets value first, then key
                value = self.stack.pop()
                key = self.stack.pop()
                self.storage[key] = value
                # print(f"[DEBUG] SSTORE: key={key}, value={value}")
            
            elif op == "SLOAD":
                self._ensure_stack(1)
                # SEMANTICS: PUSH key, SLOAD
                key = self.stack.pop()
                value = self.storage.get(key, 0)
                self.stack.append(value)
                # print(f"[DEBUG] SLOAD: key={key}, value={value}")
            
            elif op in ("LT", "GT", "EQ"):
                self._ensure_stack(2)
                b, a = self.stack.pop(), self.stack.pop()
                if op == "LT":
                    self.stack.append(1 if a < b else 0)
                elif op == "GT":
                    self.stack.append(1 if a > b else 0)
                else:
                    self.stack.append(1 if a == b else 0)
            
            elif op in ("STOP", "RETURN"):
                self.stopped = True
            
            elif op == "SHA3":
                self._ensure_stack(2)
                value = self.stack.pop() if self.stack else 0
                hash_bytes = hashlib.sha3_256(str(value).encode()).digest()
                self.stack.append(int.from_bytes(hash_bytes[:8], 'big'))
>>>>>>> e1325e33910593a6992287e350ec884bed59f946
            
            self.pc += 1
        
        return {
<<<<<<< HEAD
            "stack": self.stack.copy(),
            "storage": self.storage.copy(),
            "gas_used": self.gas_used,
            "success": self.gas_used <= self.gas_limit
        }
    
    def reset(self):
=======
            "success": not self.stopped,
            "gas_used": self.gas_used,
            "stack": self.stack.copy(),
            "storage": self.storage.copy()
        }
    
    def reset(self):
        """Reset everything including storage (for testing)"""
>>>>>>> e1325e33910593a6992287e350ec884bed59f946
        self.stack = []
        self.storage = {}
        self.gas_used = 0
        self.pc = 0
<<<<<<< HEAD
=======
        self.stopped = False
>>>>>>> e1325e33910593a6992287e350ec884bed59f946
