#!/usr/bin/env python3
"""v1.3.80: inline simple CREATE (empty / STOP init) via bridge_state."""

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


def _create_empty_bytecode(value: int = 0) -> bytes:
    """CREATE with size=0, offset=0, value."""
    return bytes(
        [
            0x60,
            value & 0xFF,  # PUSH1 value
            0x60,
            0x00,  # PUSH1 offset
            0x60,
            0x00,  # PUSH1 size
            0xF0,  # CREATE
            0x00,  # STOP (leave address on stack for observability via host marker)
        ]
    )


def _create_stop_init_bytecode(value: int = 0) -> bytes:
    """Write STOP to mem[0], CREATE size=1."""
    return bytes(
        [
            0x60,
            0x00,  # PUSH1 0
            0x60,
            0x00,  # PUSH1 0
            0x53,  # MSTORE8 mem[0]=0 (STOP)
            0x60,
            value & 0xFF,  # value
            0x60,
            0x00,  # offset
            0x60,
            0x01,  # size
            0xF0,  # CREATE
            0x00,
        ]
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_inline_create_empty_init_no_hook():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    bytecode = _create_empty_bytecode(0)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=42)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {"codes": {}, "storages": {}, "balances": {DEPLOYER: 0}}
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 1_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted"), out
    assert hook_calls["n"] == 0
    bs = host_ctx["bridge_state"]
    assert bs.get("native_inline_simple_create") is True
    addr = bs.get("native_inline_create_address")
    assert isinstance(addr, str) and addr.startswith("0x")
    expected = native.evm_deploy_address_create(DEPLOYER, 42, 0)
    assert addr.lower() == expected.lower()
    assert bs["codes"].get(addr) == ""


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_inline_create_with_value_transfers():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    bytecode = _create_empty_bytecode(7)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=1)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {},
        "storages": {},
        "balances": {DEPLOYER: 100},
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
    assert int(bal[DEPLOYER]) == 93
    assert int(bal[addr]) == 7


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_inline_create_insufficient_fails():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": True, "reverted": False, "address": "0x00", "gas_used": 1}

    bytecode = _create_empty_bytecode(50)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=1)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {},
        "storages": {},
        "balances": {DEPLOYER: 10},
    }
    evm = EVM(gas_limit=500_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    native.evm_run_nested_host_frame(bytecode, 500_000, b"", host_ctx, storage, bridge)
    assert hook_calls["n"] == 0
    assert int(host_ctx["bridge_state"]["balances"][DEPLOYER]) == 10
    assert host_ctx["bridge_state"]["codes"] == {}


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_stop_init_create_inline():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    bytecode = _create_stop_init_bytecode(0)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=9)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {"codes": {}, "storages": {}}
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 1_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted"), out
    assert hook_calls["n"] == 0
    bs = host_ctx["bridge_state"]
    assert bs.get("native_inline_simple_create") is True
    expected = native.evm_deploy_address_create(DEPLOYER, 9, 1)
    assert bs["native_inline_create_address"].lower() == expected.lower()


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_nontrivial_init_falls_to_hook():
    """Init with RETURN is not simple → Python create hook."""
    hook_calls = {"n": 0}

    def create_hook(init_code, value, caller_ctx, salt=None):
        hook_calls["n"] += 1
        return {
            "success": True,
            "reverted": False,
            "address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "gas_used": 100,
        }

    # PUSH1 0x00 PUSH1 0x00 RETURN as init in memory — not empty/STOP-only
    # Build: mstore return stub then CREATE size=4
    # Simpler: size=2 with PUSH1 STOP is not STOP-only (len!=1 or !=[0])
    bytecode = bytes(
        [
            0x60,
            0x60,  # PUSH1 0x60
            0x60,
            0x00,
            0x53,  # MSTORE8
            0x60,
            0x00,  # value
            0x60,
            0x00,  # offset
            0x60,
            0x02,  # size=2 (not eligible)
            0xF0,
            0x00,
        ]
    )
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=1)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {"codes": {}, "storages": {}}
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    native.evm_run_nested_host_frame(bytecode, 1_000_000, b"", host_ctx, storage, bridge)
    assert hook_calls["n"] == 1


def test_needles_v1380():
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "try_inline_simple_create" in rust
    assert "native_inline_simple_create" in rust
    assert "v1.3.80" in rust
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "1.3.80-industrial" in cfg
