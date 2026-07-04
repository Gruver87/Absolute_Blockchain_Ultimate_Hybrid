#!/usr/bin/env python3
"""Native EVM bytecode scan and gas helpers."""

from crypto import native
from execution.evm_bytecode_validator import validate_bytecode_hex


def test_scan_rejects_unknown_opcode():
    issues = native.evm_scan_bytecode(bytes([0x44, 0x00]))
    assert issues == [(0, 0x44)]


def test_scan_accepts_exp_opcode():
    issues = native.evm_scan_bytecode(bytes([0x60, 0x03, 0x60, 0x04, 0x0A, 0x00]))
    assert issues == []


def test_validator_accepts_sdiv_bytecode():
    # PUSH1 1 PUSH1 2 SDIV STOP
    result = validate_bytecode_hex("0x600160020500")
    assert result["valid"] is True


def test_gas_remaining_native():
    assert native.evm_gas_remaining(1_000_000, 250_000) == 750_000
