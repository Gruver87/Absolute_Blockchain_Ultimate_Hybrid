# execution/vm.py - v54 with JUMPS and FUNCTIONS
"""
EVM-style VM with jumps, function calls, loops
"""

from typing import List, Tuple, Dict, Any, Optional


class MiniVM:
    """VM with program counter, jumps, and function calls"""

    GAS_COSTS = {
        "PUSH": 2,
        "POP": 2,
        "ADD": 3,
        "SUB": 3,
        "MUL": 5,
        "DIV": 5,
        "STORE": 100,
        "LOAD": 50,
        "STOP": 0,
        "INC": 2,
        "DEC": 2,
        "EQ": 3,
        "LT": 3,
        "GT": 3,
        "NEQ": 3,
        "JUMP": 8,
        "JUMPI": 10,
        "CALL": 25,
        "RETURN": 2,
        "LABEL": 0,  # Labels consume no gas
    }

    def __init__(self, gas_limit: int = 10000):
        self.stack: List[int] = []
        self.storage: Dict[str, int] = {}
        self.gas_used = 0
        self.gas_limit = gas_limit
        self.pc = 0
        self.call_stack: List[int] = []
        self.running = True

    def _consume_gas(self, op: str):
        cost = self.GAS_COSTS.get(op, 1)
        self.gas_used += cost
        if self.gas_used > self.gas_limit:
            raise Exception(f"Out of gas! Used {self.gas_used}, limit {self.gas_limit}")

    def resolve_labels(self, code: List[Tuple[str, Optional[int]]]) -> List[Tuple[str, Optional[int]]]:
        """Resolve labels to actual PC addresses"""
        labels = {}
        pc = 0
        
        # First pass: collect label positions
        for op, arg in code:
            if op == "LABEL":
                labels[arg] = pc
            else:
                pc += 1
        
        # Second pass: replace labels in JUMP/JUMPI/CALL
        result = []
        for op, arg in code:
            if op == "LABEL":
                continue
            if op in ("JUMP", "JUMPI", "CALL") and isinstance(arg, str):
                if arg not in labels:
                    raise Exception(f"Undefined label: {arg}")
                result.append((op, labels[arg]))
            else:
                result.append((op, arg))
        
        return result

    def execute(self, bytecode: List[Tuple[str, Optional[int]]]) -> Dict[str, Any]:
        """Execute bytecode with jumps and function calls"""
        # Resolve labels first
        code = self.resolve_labels(bytecode)
        
        self.pc = 0
        self.gas_used = 0
        self.stack = []
        self.call_stack = []
        self.running = True

        while self.pc < len(code) and self.running:
            op, arg = code[self.pc]
            self._consume_gas(op)

            # Stack operations
            if op == "PUSH":
                if arg is None:
                    raise Exception("PUSH requires argument")
                self.stack.append(arg)

            elif op == "POP":
                if not self.stack:
                    raise Exception("POP on empty stack")
                self.stack.pop()

            # Arithmetic
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

            # Storage
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

            # Increment/Decrement
            elif op == "INC":
                if not self.stack:
                    self.stack.append(0)
                self.stack[-1] += 1

            elif op == "DEC":
                if not self.stack:
                    self.stack.append(0)
                self.stack[-1] -= 1

            # Comparisons
            elif op == "EQ":
                if len(self.stack) < 2:
                    raise Exception("EQ requires 2 values")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a == b else 0)

            elif op == "NEQ":
                if len(self.stack) < 2:
                    raise Exception("NEQ requires 2 values")
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a != b else 0)

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

            # Jumps
            elif op == "JUMP":
                if isinstance(arg, int):
                    self.pc = arg
                    continue
                elif len(self.stack) > 0:
                    self.pc = self.stack.pop()
                    continue
                else:
                    raise Exception("JUMP requires destination")

            elif op == "JUMPI":
                if len(self.stack) < 1:
                    raise Exception("JUMPI requires condition")
                condition = self.stack.pop()
                if condition:
                    if isinstance(arg, int):
                        self.pc = arg
                        continue
                    elif len(self.stack) > 0:
                        self.pc = self.stack.pop()
                        continue
                # else: continue to next instruction

            # Function calls
            elif op == "CALL":
                # Save return address
                self.call_stack.append(self.pc + 1)
                if isinstance(arg, int):
                    self.pc = arg
                    continue
                elif len(self.stack) > 0:
                    self.pc = self.stack.pop()
                    continue
                else:
                    raise Exception("CALL requires destination")

            elif op == "RETURN":
                if len(self.call_stack) > 0:
                    self.pc = self.call_stack.pop()
                    continue
                else:
                    # No return address, stop execution
                    self.running = False
                    break

            
            # Event logging
            elif op == "LOG":
                if len(self.stack) < 1:
                    raise Exception("LOG requires value")
                value = self.stack.pop()
                if not hasattr(self, 'logs'):
                    self.logs = []
                self.logs.append({
                    "event": str(value),
                    "data": value,
                    "pc": self.pc
                })

            
                self.running = False
                break

            else:
                raise Exception(f"Unknown opcode: {op}")

            self.pc += 1

        return {
            "stack": self.stack.copy(),
            "storage": self.storage.copy(),
            "gas_used": self.gas_used,
            "success": self.gas_used <= self.gas_limit,
            "pc": self.pc
        }

    def reset(self):
        self.stack = []
        self.storage = {}
        self.gas_used = 0
        self.pc = 0
        self.call_stack = []

    def get_storage(self, key: str) -> int:
        return self.storage.get(key, 0)

    def set_storage(self, key: str, value: int):
        self.storage[key] = value

