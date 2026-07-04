#!/usr/bin/env python3
"""Rust-backed EVM U256 arithmetic parity."""

from crypto import native


def test_evm_u256_add_matches_python_mask():
    left = (1 << 255) + 42
    right = (1 << 255) + 7
    expected = (left + right) & native.EVM_U256_MASK
    assert native.evm_u256_add(left, right) == expected


def test_evm_u256_mul_wraps():
    left = (1 << 128) + 3
    right = (1 << 128) + 5
    expected = (left * right) & native.EVM_U256_MASK
    assert native.evm_u256_mul(left, right) == expected


def test_evm_keccak256_memory_zero_size():
    digest = native.evm_keccak256_memory(b"\x01\x02", 0, 0)
    assert digest == native.keccak256_digest(b"")
