#!/usr/bin/env python3
"""Cancun-era opcodes: SGT, TLOAD, TSTORE, MCOPY."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crypto import native
from evm_interpreter import EVM, EVMContext


def test_native_sgt():
    assert native.evm_u256_sgt(10, 5) == 1
    assert native.evm_u256_sgt(5, 10) == 0
    neg = 1 << 255
    assert native.evm_u256_sgt(neg + 10, neg + 5) == 1


def test_tload_tstore_transient():
    ctx = EVMContext()
    evm = EVM(context=ctx)
    # PUSH1 42 PUSH1 0 TSTORE PUSH1 0 TLOAD STOP
    code = bytes([0x60, 42, 0x60, 0x00, 0x5D, 0x60, 0x00, 0x5C, 0x00])
    result = evm.execute_bytecode(code)
    assert result["stack"][-1] == 42


def test_mcopy_memory():
    ctx = EVMContext()
    evm = EVM(context=ctx)
    # store 0x11 at mem[32], MCOPY 32 bytes from offset 32 to offset 0
    code = bytes([
        0x60, 0x11, 0x60, 0x20, 0x52,
        0x60, 0x00, 0x60, 0x20, 0x60, 0x20, 0x5E,
        0x60, 0x00, 0x51, 0x00,
    ])
    result = evm.execute_bytecode(code)
    assert result["stack"][-1] == 0x11
