#!/usr/bin/env python3
"""Solidity-common EVM opcodes: PUSH0, CHAINID, CODESIZE, RETURN."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from evm_interpreter import EVM, EVMContext


def test_push0_and_chainid():
    ctx = EVMContext(chain_id=77777)
    evm = EVM(context=ctx)
    result = evm.execute_bytecode(bytes([0x5F, 0x46, 0x00]))
    assert result["stack"][-1] == 77777
    assert result["stack"][-2] == 0


def test_codesize_and_return():
    bytecode = bytes([0x38, 0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0xF3])
    evm = EVM()
    result = evm.execute_bytecode(bytecode)
    assert not result["reverted"]
    assert len(result["return_data"]) == 32
    assert int.from_bytes(result["return_data"], "big") == len(bytecode)


def test_revert_opcode():
    # PUSH1 0 PUSH1 0 REVERT
    evm = EVM()
    result = evm.execute_bytecode(bytes([0x60, 0x00, 0x60, 0x00, 0xFD]))
    assert result["reverted"] is True
