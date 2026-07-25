#!/usr/bin/env python3
"""v1.3.74: value=0 CALL/STATICCALL inline leaf (Priority 38 first slice)."""

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
def test_value0_call_inline_skips_hook_and_persists_storage():
    """Eligible value=0 CALL runs in Rust; hook unused; storages updated."""
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

    # Parent: CALL then STOP
    bytecode = bytes(
        [
            0x60,
            0x00,  # retSize
            0x60,
            0x00,  # retOffset
            0x60,
            0x00,  # argsSize
            0x60,
            0x00,  # argsOffset
            0x60,
            0x00,  # value = 0
            0x73,
            *bytes.fromhex(addr_hex),
            0x5A,  # GAS
            0xF1,  # CALL
            0x00,
        ]
    )
    storage: dict = {}
    ctx = EVMContext(contract_call=hook)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {callee: child_code},
        "storages": {callee: {}},
    }
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 1_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted")
    assert hook_calls["n"] == 0, "value=0 CALL leaf must skip Python hook"
    # Child storage persisted into bridge_state
    st = host_ctx["bridge_state"]["storages"][callee]
    assert int(st.get(1, st.get("1", 0))) == 99


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_value_call_still_uses_hook():
    """Non-zero value CALL must fall through to Python hook (no silent debit)."""
    child_code = bytes([0x00])  # STOP
    callee = "0x00000000000000000000000000000000000000bb"
    addr_hex = callee.replace("0x", "").zfill(40)
    hook_calls = {"n": 0}

    def hook(target, calldata, value, gas, delegate, static=False, callcode=False):
        hook_calls["n"] += 1
        assert int(value) == 1
        return {
            "success": True,
            "reverted": False,
            "return_data": b"",
            "gas_used": 10,
            "storage": {},
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
            0x60,
            0x01,  # value = 1
            0x73,
            *bytes.fromhex(addr_hex),
            0x5A,
            0xF1,
            0x00,
        ]
    )
    storage: dict = {}
    ctx = EVMContext(contract_call=hook)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {"codes": {callee: child_code}, "storages": {}}
    evm = EVM(gas_limit=500_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 500_000, b"", host_ctx, storage, bridge
    )
    assert hook_calls["n"] == 1
    assert not out.get("reverted")


def test_needles_v1374():
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "try_inline_leaf_value0_call" in rust
    assert "v1.3.74" in rust
    assert "native_inline_value0_call" in rust
