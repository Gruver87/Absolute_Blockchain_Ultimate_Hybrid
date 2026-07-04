#!/usr/bin/env python3
"""Rust-backed EVM jumpdest table and call gas helpers."""

import pytest

from crypto import native
from evm_interpreter import EVM


def test_jumpdest_not_inside_push_immediate():
    # PUSH1 0x5B ; JUMPDEST ; STOP
    bytecode = bytes([0x60, 0x5B, 0x5B, 0x00])
    table = native.evm_build_jumpdest_table(bytecode)
    assert native.evm_is_jumpdest(table, 1, len(bytecode)) is False
    assert native.evm_is_jumpdest(table, 2, len(bytecode)) is True


def test_jump_to_push_data_fails():
    bytecode = bytes([
        0x60, 0x01,       # PUSH1 1
        0x56,             # JUMP
        0x60, 0x5B,       # PUSH1 0x5B (data, not opcode)
        0x5B,             # JUMPDEST at pc=4
        0x00,             # STOP
    ])
    with pytest.raises(RuntimeError, match="invalid jump destination"):
        EVM().execute_bytecode(bytecode)


def test_jump_to_real_jumpdest_succeeds():
    bytecode = bytes([
        0x60, 0x04,       # PUSH1 4
        0x56,             # JUMP
        0x00,             # STOP (unreachable)
        0x5B,             # JUMPDEST
        0x00,             # STOP
    ])
    result = EVM().execute_bytecode(bytecode)
    assert result["reverted"] is False


def test_word_to_address_masks_to_20_bytes():
    word = int("ff" * 32, 16)
    assert native.evm_word_to_address(word) == "0x" + "ff" * 20


def test_call_gas_cap_eip150():
    assert native.evm_call_gas_cap(6400, 0) == 6300
    assert native.evm_call_gas_cap(6400, 5000) == 5000
    assert native.evm_call_gas_cap(6400, 7000) == 6300
