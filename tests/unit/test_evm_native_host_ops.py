#!/usr/bin/env python3
"""Native EVM host opcodes (CALL/CREATE) under ABS_REQUIRE_NATIVE_CRYPTO."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crypto import native
from evm_interpreter import EVM, EVMContext


pytestmark = pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)()
    or not hasattr(native, "evm_run_until_halt"),
    reason="abs_native evm_run_until_halt required",
)


@pytest.fixture
def require_native(monkeypatch):
    monkeypatch.setenv("ABS_REQUIRE_NATIVE_CRYPTO", "true")


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


def test_native_call_with_runtime_bridge(require_native):
    callee = "0x00000000000000000000000000000000000000bb"

    def hook(target, calldata, value, gas, delegate, static=False):
        assert target == callee
        assert delegate is False
        assert static is False
        return {
            "success": True,
            "reverted": False,
            "return_data": (42).to_bytes(32, "big"),
            "gas_used": 2500,
        }

    ctx = EVMContext(contract_call=hook)
    evm = EVM(gas_limit=500_000, context=ctx)
    result = evm.execute_bytecode(_build_call_bytecode(callee))
    assert result["reverted"] is False
    assert result["stack"][-1] == 42


def test_native_staticcall_with_runtime_bridge(require_native):
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


def test_native_create_with_runtime_bridge(require_native):
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


def test_native_create2_with_runtime_bridge(require_native):
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
    evm = EVM(context=EVMContext(contract_create=hook))
    evm.memory = bytearray(init)
    result = evm.execute_bytecode(bytecode)
    assert result["stack"][-1] == evm.ctx.addr_int("0x" + "aa" * 20)
    assert seen == [salt]
