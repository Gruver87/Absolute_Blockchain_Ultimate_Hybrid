"""Static EVM bytecode validation before deploy — matches evm_interpreter.py support."""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

from crypto import native

# Opcodes implemented in evm_interpreter.py (single-byte + PUSH/DUP/SWAP ranges)
_SINGLE_BYTE_SUPPORTED: Set[int] = native._EVM_SUPPORTED_SINGLE_OPCODES


def _opcode_name(op: int) -> str:
    if 0x60 <= op <= 0x7F:
        return f"PUSH{op - 0x5F}"
    if 0x80 <= op <= 0x8F:
        return f"DUP{op - 0x7F}"
    if 0x90 <= op <= 0x9F:
        return f"SWAP{op - 0x8F}"
    names = {
        0x00: "STOP", 0x01: "ADD", 0x02: "MUL", 0x03: "SUB", 0x04: "DIV",
        0x05: "SDIV", 0x06: "MOD", 0x07: "SMOD", 0x08: "ADDMOD", 0x09: "MULMOD",
        0x0A: "EXP", 0x0B: "SIGNEXTEND",
        0xF1: "CALL", 0xF3: "RETURN", 0xFD: "REVERT",
        0xF0: "CREATE", 0xF4: "DELEGATECALL", 0xFA: "STATICCALL",
        0x3B: "EXTCODESIZE", 0x3C: "EXTCODECOPY", 0x40: "BLOCKHASH",
        0x42: "TIMESTAMP", 0x43: "NUMBER", 0x45: "GASLIMIT", 0x46: "CHAINID",
        0xA0: "LOG0", 0xA1: "LOG1", 0xA2: "LOG2", 0xA3: "LOG3", 0xA4: "LOG4",
        0xFF: "SELFDESTRUCT",
        0xF2: "CALLCODE",
    }
    return names.get(op, f"0x{op:02X}")


def is_supported_opcode(op: int) -> bool:
    return native._evm_opcode_supported_python(op)


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
    for pc, op in native.evm_scan_bytecode(bytecode):
        issues.append({"pc": pc, "opcode": op, "name": _opcode_name(op)})
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
        "error": None if ok else "unsupported_opcode",
    }


def supported_opcodes_summary() -> Dict:
    singles = sorted(_opcode_name(op) for op in sorted(_SINGLE_BYTE_SUPPORTED))
    return {
        "ranges": ["PUSH1..PUSH32", "DUP1..DUP16", "SWAP1..SWAP16", "LOG0..LOG4"],
        "opcodes": singles,
    }
