#!/usr/bin/env python3
"""EVM CALL / DELEGATECALL opcodes."""
import hashlib
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

    def hook(target, calldata, value, gas, delegate, static=False):
        assert target == callee
        assert delegate is False
        assert static is False
        assert gas > 0
        return {
            "success": True,
            "reverted": False,
            "return_data": (42).to_bytes(32, "big"),
            "gas_used": 2500,
        }

    ctx = EVMContext(contract_call=hook)
    evm = EVM(gas_limit=500_000, context=ctx)
    result = evm.execute_bytecode(_build_call_bytecode(callee))
    assert result["stack"][-1] == 42
    assert result["gas_used"] >= 700 + min(2500, 100)  # CALL + capped subcall gas


def test_staticcall_readonly():
    callee = "0x00000000000000000000000000000000000000ee"

    def hook(target, calldata, value, gas, delegate, static=False):
        assert static is True
        assert value == 0
        return {
            "success": True,
            "reverted": False,
            "return_data": (7).to_bytes(32, "big"),
            "gas_used": 1200,
        }

    ctx = EVMContext(contract_call=hook)
    evm = EVM(context=ctx)
    bytecode = bytes([
        0x60, 0x20, 0x60, 0x00, 0x60, 0x00, 0x60, 0x00,
        0x73, *bytes.fromhex(callee.replace("0x", "")),
        0x60, 0x64,
        0xFA,
        0x60, 0x00, 0x51,
        0x00,
    ])
    result = evm.execute_bytecode(bytecode)
    assert result["stack"][-1] == 7


def test_create_opcode_with_hook():
    created = "0x" + "dd" * 20

    def create_hook(init_code, value, ctx, salt=None):
        assert value == 0
        assert len(init_code) > 0
        return {"success": True, "address": created, "gas_used": 8000}

    ctx = EVMContext(contract_create=create_hook)
    evm = EVM(context=ctx)
    init = bytes.fromhex("60006000f3")
    evm.memory = bytearray(init)
    bytecode = bytes([
        0x60, 0x00,
        0x60, 0x00,
        0x60, len(init),
        0xF0,
        0x00,
    ])
    result = evm.execute_bytecode(bytecode)
    assert result["stack"][-1] == ctx.addr_int(created)


def test_create2_opcode_with_salt():
    salt = 0x42
    seen = []

    def hook(init_code, value, ctx, salt_arg=None):
        seen.append(salt_arg)
        return {"success": True, "address": "0x" + "aa" * 20, "gas_used": 9000}

    init = bytes.fromhex("60006000f3")
    bytecode = bytes([
        0x60, 0x00,
        0x60, 0x00,
        0x60, len(init),
        0x60, salt & 0xFF,
        0xF5,
        0x00,
    ])
    evm1 = EVM(context=EVMContext(contract_create=hook))
    evm1.memory = bytearray(init)
    r1 = evm1.execute_bytecode(bytecode)
    evm2 = EVM(context=EVMContext(contract_create=hook))
    evm2.memory = bytearray(init)
    r2 = evm2.execute_bytecode(bytecode)
    assert r1["stack"][-1] == r2["stack"][-1]
    assert seen == [salt, salt]


def test_call_stipend_forwarded_with_value():
    seen = {}

    def hook(target, calldata, value, gas, delegate, static=False):
        seen["value"] = value
        seen["gas"] = gas
        return {"success": True, "reverted": False, "return_data": b"", "gas_used": 500}

    ctx = EVMContext(contract_call=hook)
    evm = EVM(gas_limit=500_000, context=ctx)
    callee = "0x" + "ee" * 20
    bytecode = bytes([
        0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0x60, 0x00,
        0x60, 0x01,
        0x73, *bytes.fromhex(callee.replace("0x", "")),
        0x60, 0x64,
        0xF1,
        0x00,
    ])
    evm.execute_bytecode(bytecode)
    assert seen["value"] == 1
    assert seen["gas"] >= EVM.CALL_STIPEND


def test_delegatecall_merges_storage():
    callee = "0x00000000000000000000000000000000000000cc"
    merged = {}

    def hook(target, calldata, value, gas, delegate, static=False):
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


def test_adapter_staticcall_between_contracts(evm_db):
    adapter, db = evm_db
    deployer = "0xdeployer000000000000000000000000000001"
    db.save_account(deployer, balance=100.0, nonce=0)

    callee_bc = "602a60005260206000f3"
    callee = adapter.deploy_contract(deployer, callee_bc, salt="callee2")
    assert callee.success

    addr_hex = callee.return_value.replace("0x", "").lower().zfill(40)
    static_caller = bytes([
        0x60, 0x20, 0x60, 0x00, 0x60, 0x00, 0x60, 0x00,
        0x73, *bytes.fromhex(addr_hex),
        0x60, 0x64,
        0xFA,
        0x60, 0x00, 0x51,
        0x00,
    ]).hex()
    caller = adapter.deploy_contract(deployer, static_caller, salt="static-caller")
    assert caller.success
    out = adapter.call_contract(deployer, caller.return_value, "")
    assert out.success, out.error
    assert out.return_value == 42


def test_adapter_create_deploys_child(evm_db):
    adapter, db = evm_db
    deployer = "0xdeployer000000000000000000000000000001"
    db.save_account(deployer, balance=100.0, nonce=0)

    init = bytes.fromhex("602a60005260206000f3")
    init_len = len(init)
    prefix = bytes([
        0x60, init_len, 0x60, 15, 0x60, 0x00, 0x39,
        0x60, 0x00, 0x60, 0x00, 0x60, init_len, 0xF0, 0x00,
    ])
    factory = adapter.deploy_contract(deployer, (prefix + init).hex(), salt="factory")
    assert factory.success, factory.error

    factory_addr = factory.return_value
    child_seed = f"{factory_addr}{adapter._make_context('', factory_addr).block_number}{init_len}"
    child_addr = "0x" + hashlib.sha256(child_seed.encode()).hexdigest()[:40]
    child = adapter.get_contract_info(child_addr)
    assert child.get("is_contract") is True


def test_adapter_create2_deploys_child(evm_db):
    adapter, db = evm_db
    deployer = "0xdeployer000000000000000000000000000001"
    db.save_account(deployer, balance=100.0, nonce=0)

    salt = 0x42
    init = bytes.fromhex("602a60005260206000f3")
    init_len = len(init)
    prefix = bytes([
        0x60, init_len, 0x60, 17, 0x60, 0x00, 0x39,
        0x60, 0x00, 0x60, 0x00, 0x60, init_len,
        0x60, salt & 0xFF,
        0xF5, 0x00,
    ])
    factory = adapter.deploy_contract(deployer, (prefix + init).hex(), salt="factory2")
    assert factory.success, factory.error

    factory_addr = factory.return_value
    child_seed = f"create2:{factory_addr}:{salt}:{init.hex()}"
    child_addr = "0x" + hashlib.sha256(child_seed.encode()).hexdigest()[:40]
    child = adapter.get_contract_info(child_addr)
    assert child.get("is_contract") is True
