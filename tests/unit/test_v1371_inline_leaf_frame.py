#!/usr/bin/env python3
"""v1.3.71: in-Rust inline leaf frame for eligible DELEGATECALL (Priority 37)."""

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


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_inline_leaf_delegatecall_skips_python_hook():
    """Eligible DELEGATECALL child runs in Rust; contract_call hook must not fire."""
    # Child: PUSH1 99 PUSH1 1 SSTORE STOP
    child_code = bytes([0x60, 0x63, 0x60, 0x01, 0x55, 0x00])
    callee = "0x00000000000000000000000000000000000000bb"
    addr_hex = callee.replace("0x", "").zfill(40)
    hook_calls = {"n": 0}

    def hook(target, calldata, value, gas, delegate, static=False, callcode=False):
        hook_calls["n"] += 1
        return {
            "success": False,
            "reverted": True,
            "return_data": b"",
            "gas_used": 0,
            "storage": {},
        }

    # Parent: SSTORE(1,42) ; DELEGATECALL ; SLOAD(1) STOP
    bytecode = bytes(
        [
            0x60,
            0x2A,
            0x60,
            0x01,
            0x55,
            0x60,
            0x00,
            0x60,
            0x00,
            0x60,
            0x00,
            0x60,
            0x00,
            0x73,
            *bytes.fromhex(addr_hex),
            0x5A,
            0xF4,
            0x50,
            0x60,
            0x01,
            0x54,
            0x00,
        ]
    )
    storage: dict = {}
    ctx = EVMContext(
        contract_call=hook,
        address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {"codes": {callee: child_code}}
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode,
        1_000_000,
        b"",
        host_ctx,
        storage,
        bridge,
    )
    assert not out.get("reverted")
    assert hook_calls["n"] == 0, "inline leaf must skip Python contract_call"
    assert int(storage.get(1, 0)) == 99


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_ineligible_child_still_uses_hook():
    """Child with CALL opcode is not leaf-eligible → Python hook path."""
    # Child contains CALL (0xF1) — not nested_native_eligible
    child_code = bytes([0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0xF1, 0x00])
    callee = "0x00000000000000000000000000000000000000bb"
    addr_hex = callee.replace("0x", "").zfill(40)
    hook_calls = {"n": 0}

    def hook(target, calldata, value, gas, delegate, static=False, callcode=False):
        hook_calls["n"] += 1
        return {
            "success": True,
            "reverted": False,
            "return_data": b"",
            "gas_used": 10,
            "storage": {1: 7},
        }

    bytecode = bytes(
        [
            0x60,
            0x00,
            0x60,
            0x00,
            0x60,
            0x00,
            0x60,
            0x00,
            0x73,
            *bytes.fromhex(addr_hex),
            0x5A,
            0xF4,
            0x00,
        ]
    )
    storage: dict = {}
    ctx = EVMContext(contract_call=hook)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {"codes": {callee: child_code}}
    evm = EVM(gas_limit=500_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 500_000, b"", host_ctx, storage, bridge
    )
    assert hook_calls["n"] == 1
    assert not out.get("reverted")
    assert int(storage.get(1, 0)) == 7


def test_needles_v1371():
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "try_inline_leaf_delegate_call" in rust
    assert "v1.3.71" in rust
    assert "bytecode_is_nested_native_eligible" in rust
    assert native.evm_bytecode_is_nested_native_eligible(bytes([0x00])) is True
    assert native.evm_bytecode_is_nested_native_eligible(bytes([0xF1, 0x00])) is False
