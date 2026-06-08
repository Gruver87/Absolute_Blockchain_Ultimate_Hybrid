# compiler/assembler.py
"""
Assembler with labels, jumps, functions
Converts assembly to bytecode
"""

import re
from typing import List, Tuple, Optional


class Assembler:
    """Assembly compiler with label support"""
    
    def __init__(self):
        self.labels = {}
        self.code = []
        self.pending = []  # (position, label)
    
    def assemble(self, source: str) -> List[Tuple[str, Optional[int]]]:
        """Compile assembly source to bytecode"""
        lines = source.strip().split('\n')
        self.code = []
        self.labels = {}
        self.pending = []
        
        # First pass: collect labels
        pc = 0
        for line in lines:
            line = self._clean(line)
            if not line:
                continue
            
            if line.endswith(':'):
                label = line[:-1]
                self.labels[label] = pc
                continue
            
            # Parse instruction
            parts = line.split()
            op = parts[0].upper()
            arg = None
            if len(parts) > 1:
                arg_str = ' '.join(parts[1:])
                if arg_str.isdigit():
                    arg = int(arg_str)
                elif arg_str.startswith('0x'):
                    arg = int(arg_str, 16)
                else:
                    # Could be a label or string key
                    arg = arg_str
            
            self.code.append((op, arg))
            pc += 1
        
        # Second pass: resolve label references
        result = []
        for op, arg in self.code:
            if op in ("JUMP", "JUMPI", "CALL") and isinstance(arg, str):
                if arg not in self.labels:
                    raise Exception(f"Undefined label: {arg}")
                result.append((op, self.labels[arg]))
            else:
                result.append((op, arg))
        
        return result
    
    def _clean(self, line: str) -> str:
        """Remove comments and whitespace"""
        if ';' in line:
            line = line[:line.index(';')]
        return line.strip()


def assemble(source: str) -> List[Tuple[str, Optional[int]]]:
    """Convenience function"""
    return Assembler().assemble(source)


def disassemble(bytecode: List[Tuple[str, Optional[int]]]) -> str:
    """Convert bytecode back to assembly"""
    lines = []
    for op, arg in bytecode:
        if arg is not None:
            lines.append(f"    {op} {arg}")
        else:
            lines.append(f"    {op}")
    return '\n'.join(lines)
