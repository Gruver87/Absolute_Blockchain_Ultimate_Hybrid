"""Static EVM bytecode validation before deploy — matches evm_interpreter.py support."""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

# Opcodes implemented in evm_interpreter.py (single-byte + PUSH/DUP/SWAP ranges)
_SINGLE_BYTE_SUPPORTED: Set[int] = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x06,
    0x10, 0x11, 0x12, 0x14, 0x15, 0x16, 0x17, 0x19, 0x1A, 0x1B, 0x1C,
    0x20,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39,
    0x3B, 0x3C, 0x3D, 0x3E, 0x40,
    0xA0, 0xA1, 0xA2, 0xA3, 0xA4,
    0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x5A, 0x5B, 0x5F,
    0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xFA, 0xFD, 0xFE, 0xFF,
}


def _opcode_name(op: int) -> str:
    if 0x60 <= op <= 0x7F:
        return f"PUSH{op - 0x5F}"
    if 0x80 <= op <= 0x8F:
        return f"DUP{op - 0x7F}"
    if 0x90 <= op <= 0x9F:
        return f"SWAP{op - 0x8F}"
    names = {
        0x00: "STOP", 0x01: "ADD", 0x02: "MUL", 0x03: "SUB", 0x04: "DIV",
        0x06: "MOD", 0xF1: "CALL", 0xF3: "RETURN", 0xFD: "REVERT",
        0xF0: "CREATE", 0xF4: "DELEGATECALL", 0xFA: "STATICCALL",
        0x3B: "EXTCODESIZE", 0x3C: "EXTCODECOPY", 0x40: "BLOCKHASH",
        0xA0: "LOG0", 0xA1: "LOG1", 0xA2: "LOG2", 0xA3: "LOG3", 0xA4: "LOG4",
        0xFF: "SELFDESTRUCT",
        0xF2: "CALLCODE",
    }
    return names.get(op, f"0x{op:02X}")


def is_supported_opcode(op: int) -> bool:
    if 0x60 <= op <= 0x7F or 0x80 <= op <= 0x8F or 0x90 <= op <= 0x9F:
        return True
    return op in _SINGLE_BYTE_SUPPORTED


def parse_bytecode(raw: str) -> bytes:
    s = (raw or "").strip()
    if s.startswith("0x") or s.startswith("0X"):
        s = s[2:]
    s = s.replace(" ", "")
    if not s:
        return b""
    if len(s) % 2:
        raise ValueError("invalid_hex_length")
    return bytes.fromhex(s)


def scan_bytecode(bytecode: bytes) -> Tuple[bool, List[Dict]]:
    """Return (valid, issues) where issues list unsupported opcodes with PC."""
    issues: List[Dict] = []
    pc = 0
    while pc < len(bytecode):
        op = bytecode[pc]
        if not is_supported_opcode(op):
            issues.append({"pc": pc, "opcode": op, "name": _opcode_name(op)})
        if 0x60 <= op <= 0x7F:
            push_size = op - 0x5F
            pc += 1 + push_size
        else:
            pc += 1
    return len(issues) == 0, issues


def validate_bytecode_hex(raw: str) -> Dict:
    try:
        code = parse_bytecode(raw)
    except ValueError as e:
        return {"valid": False, "error": str(e), "size": 0, "unsupported": []}
    if not code:
        return {"valid": False, "error": "empty_bytecode", "size": 0, "unsupported": []}
    ok, issues = scan_bytecode(code)
    return {
        "valid": ok,
        "size": len(code),
        "unsupported": issues,
        "supported_opcodes": len(_SINGLE_BYTE_SUPPORTED) + 48 + 16 + 16,
    }


def supported_opcodes_summary() -> Dict:
    singles = sorted(_opcode_name(o) for o in sorted(_SINGLE_BYTE_SUPPORTED))
    return {
        "ranges": ["PUSH1..PUSH32", "DUP1..DUP16", "SWAP1..SWAP16"],
        "opcodes": singles,
        "note": "DIFFICULTY not supported; BLOCKHASH, CALLCODE, LOG, EXTCODE*, SELFDESTRUCT supported",
    }
