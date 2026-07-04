#!/usr/bin/env python3
"""Rust-backed EVM PUSH decode parity."""

from crypto import native


def test_evm_read_push_single_byte():
    bytecode = bytes([0x60, 0x2A, 0x00])
    assert native.evm_read_push(bytecode, 0, 1) == 42


def test_evm_read_push_pads_short_bytecode():
    bytecode = bytes([0x61, 0x01, 0x02])
    assert native.evm_read_push(bytecode, 0, 2) == int.from_bytes(b"\x01\x02", "big")


def test_evm_read_push32():
    payload = bytes(range(1, 33))
    bytecode = bytes([0x7F]) + payload + bytes([0x00])
    assert native.evm_read_push(bytecode, 0, 32) == int.from_bytes(payload, "big")
