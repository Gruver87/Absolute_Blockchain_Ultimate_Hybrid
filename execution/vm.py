# execution/vm.py - FULLY FIXED
from typing import List, Tuple, Dict, Any, Optional

class MiniVM:
    GAS_COSTS = {
        "PUSH": 2, "POP": 2, "ADD": 3, "SUB": 3, "MUL": 5, "DIV": 5,
        "STORE": 20, "SSTORE": 20, "MSTORE": 20, "LOAD": 20, "SLOAD": 20, "MLOAD": 20, "STOP": 0, "INC": 2, "DEC": 2,
        "EQ": 3, "LT": 3, "GT": 3, "JUMP": 1, "JUMPI": 1,
    }
    
    def __init__(self, gas_limit: int = 10000):
        self.stack: List[int] = []
        self.storage: Dict[int, int] = {}
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
        self.running = True
        
        while self.pc < len(bytecode) and self.running:
            op, arg = bytecode[self.pc]
            self._consume_gas(op)
            
            if op == "PUSH":
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
                self.stack.append(a - b)  # a - b = ˜˜˜˜˜˜˜˜˜˜ ˜˜˜˜˜˜˜
            elif op == "MUL":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)
            elif op == "DIV":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a // b if b != 0 else 0)
            elif op == "STORE" or op == "SSTORE" or op == "MSTORE":
                value = self.stack.pop()
                key = self.stack.pop()
                self.storage[key] = value
            elif op == "LOAD" or op == "SLOAD" or op == "MLOAD":
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
            
            self.pc += 1
        
        return {
            "stack": self.stack.copy(),
            "storage": self.storage.copy(),
            "gas_used": self.gas_used,
            "success": self.gas_used <= self.gas_limit
        }
    
    def reset(self):
        self.stack = []
        self.storage = {}
        self.gas_used = 0
        self.pc = 0
