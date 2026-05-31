# execution/vm.py - FIXED VERSION
"""
Mini-EVM — bytecode VM with stack, storage, gas metering
"""

from typing import List, Tuple, Dict, Any, Optional


class MiniVM:
    """Simplified Ethereum Virtual Machine"""
    
    GAS_COSTS = {
        "PUSH": 2, "POP": 2, "ADD": 3, "SUB": 3, "MUL": 5, "DIV": 5,
        "STORE": 100, "LOAD": 50, "STOP": 0, "INC": 2, "DEC": 2,
        "EQ": 3, "LT": 3, "GT": 3, "JUMP": 8, "JUMPI": 10, "CALL": 25, "RETURN": 2
    }

    def __init__(self, gas_limit: int = 10000):
        self.stack: List[int] = []
        self.storage: Dict[str, int] = {}
        self.gas_used = 0
        self.gas_limit = gas_limit
        self.pc = 0
        self.running = True
        self.call_stack: List[int] = []

    def _consume_gas(self, op: str):
        cost = self.GAS_COSTS.get(op, 1)
        self.gas_used += cost
        if self.gas_used > self.gas_limit:
            raise Exception(f"Out of gas! Used {self.gas_used}, limit {self.gas_limit}")

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
                if not self.stack:
                    raise Exception("POP on empty stack")
                self.stack.pop()

            elif op == "ADD":
                if len(self.stack) < 2:
                    raise Exception("ADD requires 2 values")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a + b)

            elif op == "SUB":
                if len(self.stack) < 2:
                    raise Exception("SUB requires 2 values")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)

            elif op == "MUL":
                if len(self.stack) < 2:
                    raise Exception("MUL requires 2 values")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)

            elif op == "DIV":
                if len(self.stack) < 2:
                    raise Exception("DIV requires 2 values")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a // b if b != 0 else 0)

            elif op == "STORE":
                if len(self.stack) < 2:
                    raise Exception("STORE requires key and value")
                key = str(self.stack.pop())
                value = self.stack.pop()
                self.storage[key] = value

            elif op == "LOAD":
                if not self.stack:
                    raise Exception("LOAD requires key")
                key = str(self.stack.pop())
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
                if len(self.stack) < 2:
                    raise Exception("EQ requires 2 values")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a == b else 0)

            elif op == "LT":
                if len(self.stack) < 2:
                    raise Exception("LT requires 2 values")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a < b else 0)

            elif op == "GT":
                if len(self.stack) < 2:
                    raise Exception("GT requires 2 values")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a > b else 0)

            elif op == "JUMP":
                if not self.stack:
                    raise Exception("JUMP requires destination")
                dest = self.stack.pop()
                if 0 <= dest < len(bytecode):
                    self.pc = dest
                    continue
                raise Exception(f"Invalid jump destination: {dest}")

            elif op == "JUMPI":
                if len(self.stack) < 2:
                    raise Exception("JUMPI requires destination and condition")
                dest = self.stack.pop()
                cond = self.stack.pop()
                if cond != 0:
                    if 0 <= dest < len(bytecode):
                        self.pc = dest
                        continue
                    raise Exception(f"Invalid jump destination: {dest}")

            elif op == "CALL":
                if not self.stack:
                    raise Exception("CALL requires destination")
                dest = self.stack.pop()
                self.call_stack.append(self.pc + 1)
                if 0 <= dest < len(bytecode):
                    self.pc = dest
                    continue
                raise Exception(f"Invalid call destination: {dest}")

            elif op == "RETURN":
                if self.call_stack:
                    self.pc = self.call_stack.pop()
                    continue
                self.running = False
                break

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
        self.call_stack = []

    def get_storage(self, key: str) -> int:
        return self.storage.get(key, 0)
