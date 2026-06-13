#!/usr/bin/env python3
"""EVM CALL / DELEGATECALL opcodes."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from evm_interpreter import EVM, EVMContext
from execution.evm_adapter import EVMAdapter
from runtime.config import Config
from storage.database import Database


@pytest.fixture
def evm_db(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "evm.db")
    db = Database(cfg.db_path, synchronous="NORMAL")
    db.initialize()
    yield EVMAdapter(db, cfg), db
    db.close()


def _build_call_bytecode(target: str) -> bytes:
    addr_hex = target.replace("0x", "").lower().zfill(40)
    return bytes([
        0x60, 0x20,
        0x60, 0x00,
        0x60, 0x00,
        0x60, 0x00,
        0x60, 0x00,
        0x73, *bytes.fromhex(addr_hex),
        0x60, 0x64,
        0xF1,
        0x60, 0x00, 0x51,
        0x00,
    ])


def test_call_opcode_with_hook():
    callee = "0x00000000000000000000000000000000000000bb"

    def hook(target, calldata, value, gas, delegate):
        assert target == callee
        assert delegate is False
        return {
            "success": True,
            "reverted": False,
            "return_data": (42).to_bytes(32, "big"),
        }

    ctx = EVMContext(contract_call=hook)
    evm = EVM(context=ctx)
    result = evm.execute_bytecode(_build_call_bytecode(callee))
    assert result["stack"][-1] == 42


def test_delegatecall_merges_storage():
    callee = "0x00000000000000000000000000000000000000cc"
    merged = {}

    def hook(target, calldata, value, gas, delegate):
        assert delegate is True
        merged[7] = 99
        return {"success": True, "reverted": False, "return_data": b"", "storage": merged}

    ctx = EVMContext(contract_call=hook, address="0x" + "aa" * 20)
    evm = EVM(context=ctx)
    evm.storage = {1: 5}
    bytecode = bytes([
        0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0x60, 0x00,
        0x73, *bytes.fromhex(callee.replace("0x", "")),
        0x60, 0x64,
        0xF4,
        0x00,
    ])
    result = evm.execute_bytecode(bytecode)
    assert result["storage"].get(7) == 99


def test_adapter_call_between_contracts(evm_db):
    adapter, db = evm_db
    deployer = "0xdeployer000000000000000000000000000001"
    db.save_account(deployer, balance=100.0, nonce=0)

    callee_bc = "602a60005260206000f3"  # return 42
    callee = adapter.deploy_contract(deployer, callee_bc, salt="callee")
    assert callee.success, callee.error

    caller_bc = _build_call_bytecode(callee.return_value).hex()
    caller = adapter.deploy_contract(deployer, caller_bc, salt="caller")
    assert caller.success, caller.error

    out = adapter.call_contract(deployer, caller.return_value, "")
    assert out.success, out.error
    assert out.return_value == 42
