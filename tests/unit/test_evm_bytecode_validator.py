#!/usr/bin/env python3
"""EVM bytecode static validator tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from execution.evm_bytecode_validator import validate_bytecode_hex, supported_opcodes_summary


def test_valid_simple_bytecode():
    # PUSH1 5 PUSH1 7 ADD STOP
    v = validate_bytecode_hex("0x600560070100")
    assert v["valid"] is True
    assert v["size"] == 6


def test_accepts_log0_opcode():
    # LOG0 = 0xA0 with stack setup: PUSH0 PUSH0 LOG0 STOP
    v = validate_bytecode_hex("0x5f5fa000")
    assert v["valid"] is True


def test_rejects_difficulty_opcode():
    v = validate_bytecode_hex("0x4400")
    assert v["valid"] is False


def test_supported_summary():
    s = supported_opcodes_summary()
    assert "PUSH1..PUSH32" in s["ranges"]
    assert "CALL" in s["opcodes"]
