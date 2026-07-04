#!/usr/bin/env python3
"""Rust-backed EVM compare/memory opcode parity."""

from crypto import native


def test_evm_u256_cmp_ops():
    assert native.evm_u256_eq(42, 42) == 1
    assert native.evm_u256_eq(42, 43) == 0
    assert native.evm_u256_lt(1, 2) == 1
    assert native.evm_u256_lt(2, 1) == 0
    assert native.evm_u256_gt(5, 3) == 1
    assert native.evm_u256_iszero(0) == 1
    assert native.evm_u256_iszero(9) == 0


def test_evm_u256_byte_msb():
    word = int.from_bytes(bytes([0xAB] + [0x00] * 31), "big")
    assert native.evm_u256_byte(0, word) == 0xAB
    assert native.evm_u256_byte(31, word) == 0
    assert native.evm_u256_byte(32, word) == 0


def test_evm_memory_read_word_zero_pad():
    memory = b"\x01\x02\x03"
    assert native.evm_memory_read_word(memory, 0) == int.from_bytes(
        b"\x01\x02\x03" + b"\x00" * 29, "big"
    )


def test_evm_calldataload_zero_pad():
    data = b"\xaa\xbb"
    assert native.evm_calldataload(data, 0) == int.from_bytes(
        b"\xaa\xbb" + b"\x00" * 30, "big"
    )


def test_evm_memory_copy_zero_fills():
    memory = bytearray(8)
    native.evm_memory_copy(memory, 2, b"\x11", 0, 4)
    assert bytes(memory) == b"\x00\x00\x11\x00\x00\x00\x00\x00"
