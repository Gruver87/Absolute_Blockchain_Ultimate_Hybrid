#!/usr/bin/env python3
"""EVM SHA3 opcode uses Ethereum Keccak-256 via native kernel."""

from crypto import native
from evm_interpreter import EVM


def test_evm_sha3_opcode_uses_keccak256():
    # PUSH1 0 (size), PUSH1 0 (offset), SHA3 => keccak256(b"")
    code = bytes([0x60, 0x00, 0x60, 0x00, 0x20, 0x00])
    evm = EVM()
    result = evm.execute_bytecode(code)
    assert not result["reverted"]
    expected = int.from_bytes(native.keccak256_digest(b""), "big")
    assert result["stack"][-1] == expected
