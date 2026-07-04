#!/usr/bin/env python3
"""Solidity 0.8+ opcodes: SLT, SAR, PC, MSIZE, SELFBALANCE, BASEFEE."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crypto import native
from evm_interpreter import EVM, EVMContext


def test_native_slt_sar_vectors():
    neg = 1 << 255
    assert native.evm_u256_slt(neg + 1, neg + 5) == 1
    assert native.evm_u256_slt(5, 10) == 1
    mask = (native.EVM_U256_MASK << (256 - 4)) & native.EVM_U256_MASK
    assert native.evm_u256_sar(neg | 0xFF, 4) == ((neg | 0xFF) >> 4) | mask


def test_pc_msize_selfbalance_basefee():
    addr = "0x00000000000000000000000000000000000000ab"
    ctx = EVMContext(
        address=addr,
        base_fee=7,
        balance_of=lambda who: 42 if who.lower() == addr.lower() else 0,
    )
    evm = EVM(context=ctx)
    # MSIZE after MSTORE8 at 0 -> 32; BASEFEE; SELFBALANCE
    result = evm.execute_bytecode(bytes([0x60, 0x01, 0x60, 0x00, 0x53, 0x59, 0x48, 0x47, 0x00]))
    assert result["stack"][-1] == 42
    assert result["stack"][-2] == 7
    assert result["stack"][-3] == 32

    evm2 = EVM(context=ctx)
    # PUSH1 0 JUMPDEST PC -> PC pushes offset of the PC opcode itself (3)
    r2 = evm2.execute_bytecode(bytes([0x60, 0x00, 0x5B, 0x58, 0x00]))
    assert r2["stack"][-1] == 3
