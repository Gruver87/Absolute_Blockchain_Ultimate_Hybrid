#!/usr/bin/env python3
"""Rust-backed EVM stack and memory slice helpers."""

import pytest

from crypto import native
from evm_interpreter import EVM


def test_stack_dup_swap_native():
    stack = [1, 2, 3]
    native.evm_stack_dup(stack, 1)
    assert stack == [1, 2, 3, 3]
    native.evm_stack_swap(stack, 1)
    assert stack == [1, 2, 3, 3]


def test_stack_dup2_copies_second_from_top():
    stack = [1, 2]
    native.evm_stack_dup(stack, 2)
    assert stack == [1, 2, 1]


def test_stack_dup_underflow_raises():
    with pytest.raises(RuntimeError, match="stack underflow"):
        native.evm_stack_dup([], 1)


def test_memory_slice_zero_pads():
    memory = b"\xaa\xbb"
    assert native.evm_memory_slice(memory, 1, 4) == b"\xbb\x00\x00\x00"


def test_interpreter_dup1_opcode():
    result = EVM().execute_bytecode(bytes([0x60, 0x01, 0x60, 0x02, 0x80, 0x00]))
    assert result["stack"] == [1, 2, 2]


def test_interpreter_swap1_opcode():
    result = EVM().execute_bytecode(bytes([0x60, 0x01, 0x60, 0x02, 0x90, 0x00]))
    assert result["stack"] == [2, 1]
