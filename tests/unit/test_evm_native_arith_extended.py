#!/usr/bin/env python3
"""Rust-backed extended EVM arithmetic opcode parity."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crypto import native
from evm_interpreter import EVM


MASK = native.EVM_U256_MASK
MIN_I256 = 1 << 255


def test_sdiv_smod_native():
    assert native.evm_u256_sdiv(0, 7) == 0
    assert native.evm_u256_sdiv(7, 0) == 0
    assert native.evm_u256_sdiv(MIN_I256, MASK) == MIN_I256
    neg17 = (-17) & MASK
    assert native.evm_u256_smod(neg17, 5) == ((-2) & MASK)


def test_addmod_mulmod_native():
    assert native.evm_u256_addmod(MASK, 2, 5) == 2
    assert native.evm_u256_addmod(1, 2, 0) == 0
    assert native.evm_u256_mulmod(3, 4, 5) == 2
    assert native.evm_u256_mulmod(1, 2, 0) == 0


def test_exp_native():
    assert native.evm_u256_exp(0, 0) == 0
    assert native.evm_u256_exp(3, 0) == 1
    assert native.evm_u256_exp(3, 4) == 81
    assert native.evm_u256_exp(2, 256) == 0


def test_signextend_native():
    assert native.evm_u256_signextend(0, 0x80) == (MASK ^ 0x7F) | 0x80
    assert native.evm_u256_signextend(0, 0x7F) == 0x7F
    assert native.evm_u256_signextend(32, 0x1234) == 0x1234


def test_interpreter_exp_and_signextend_opcodes():
    # PUSH1 3 PUSH1 4 EXP STOP -> 3 ** 4
    exp_result = EVM().execute_bytecode(bytes([0x60, 0x03, 0x60, 0x04, 0x0A, 0x00]))
    assert exp_result["stack"][-1] == 81

    # PUSH1 0x80 PUSH1 0 SIGNEXTEND STOP
    sign_result = EVM().execute_bytecode(bytes([0x60, 0x80, 0x60, 0x00, 0x0B, 0x00]))
    assert sign_result["stack"][-1] == native.evm_u256_signextend(0, 0x80)


def test_interpreter_mstore_native():
    # PUSH1 0xAB PUSH1 31 MSTORE8 STOP
    result = EVM().execute_bytecode(bytes([0x60, 0xAB, 0x60, 0x1F, 0x53, 0x00]))
    assert result["memory"][31] == 0xAB
