#!/usr/bin/env python3
"""v1.3.81: inline CREATE2 (empty/STOP init) via EIP-1014 / legacy."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native
from evm_interpreter import EVM, EVMContext
from execution.evm_host_bridge import make_evm_runtime_bridge


DEPLOYER = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _create2_empty_bytecode(salt: int = 1, value: int = 0) -> bytes:
    """CREATE2: value, offset=0, size=0, salt."""
    return bytes(
        [
            0x60,
            value & 0xFF,
            0x60,
            0x00,  # offset
            0x60,
            0x00,  # size
            0x60,
            salt & 0xFF,  # salt
            0xF5,  # CREATE2
            0x00,
        ]
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_inline_create2_eip1014_empty_init():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    salt = 7
    bytecode = _create2_empty_bytecode(salt=salt, value=0)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=1)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {},
        "storages": {},
        "create2_eip1014": True,
    }
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 1_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted"), out
    assert hook_calls["n"] == 0
    bs = host_ctx["bridge_state"]
    assert bs.get("native_inline_create2") is True
    assert bs.get("native_inline_create2_eip1014") is True
    addr = bs["native_inline_create_address"]
    expected = native.evm_create2_address_eip1014(DEPLOYER, salt, b"")
    assert addr.lower() == expected.lower()
    assert bs["codes"].get(addr) == ""


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_inline_create2_legacy_when_flag_false():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    salt = 3
    bytecode = _create2_empty_bytecode(salt=salt)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=1)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {},
        "storages": {},
        "create2_eip1014": False,
    }
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 1_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted"), out
    assert hook_calls["n"] == 0
    bs = host_ctx["bridge_state"]
    assert bs.get("native_inline_create2") is True
    assert bs.get("native_inline_create2_eip1014") is False
    addr = bs["native_inline_create_address"]
    expected = native.evm_deploy_address_create2_legacy(DEPLOYER, salt, b"")
    assert addr.lower() == expected.lower()


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_inline_create2_value_transfer():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    bytecode = _create2_empty_bytecode(salt=1, value=5)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=1)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {},
        "storages": {},
        "balances": {DEPLOYER: 40},
        "create2_eip1014": True,
    }
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 1_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted"), out
    assert hook_calls["n"] == 0
    addr = host_ctx["bridge_state"]["native_inline_create_address"]
    bal = host_ctx["bridge_state"]["balances"]
    assert int(bal[DEPLOYER]) == 35
    assert int(bal[addr]) == 5


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_create2_nontrivial_init_falls_to_hook():
    hook_calls = {"n": 0}

    def create_hook(init_code, value, caller_ctx, salt=None):
        hook_calls["n"] += 1
        assert salt is not None
        return {
            "success": True,
            "reverted": False,
            "address": "0xcccccccccccccccccccccccccccccccccccccccc",
            "gas_used": 50,
        }

    # size=1 with CREATE opcode in init → not leaf-eligible
    bytecode = bytes(
        [
            0x60,
            0xF0,  # PUSH1 CREATE
            0x60,
            0x00,
            0x53,  # MSTORE8
            0x60,
            0x00,  # value
            0x60,
            0x00,  # offset
            0x60,
            0x01,  # size
            0x60,
            0x01,  # salt
            0xF5,
            0x00,
        ]
    )
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=1)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {"codes": {}, "storages": {}, "create2_eip1014": True}
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    native.evm_run_nested_host_frame(bytecode, 1_000_000, b"", host_ctx, storage, bridge)
    assert hook_calls["n"] == 1


def test_needles_v1381():
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "native_inline_create2" in rust
    assert "create2_eip1014_enabled" in rust
    assert "v1.3.81" in rust
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    notes = (ROOT / "RELEASE_NOTES_v1.3.81.md").read_text(encoding="utf-8")
    assert "1.3.81-industrial" in notes
    assert "native_inline_create2" in rust
