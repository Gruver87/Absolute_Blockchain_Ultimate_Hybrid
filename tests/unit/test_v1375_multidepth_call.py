#!/usr/bin/env python3
"""v1.3.75: multi-depth value=0 CALL frames (Priority 38)."""

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


def _call_bytecode(to_addr: str) -> bytes:
    """Minimal value=0 CALL to to_addr then STOP."""
    addr_hex = to_addr.replace("0x", "").zfill(40)
    return bytes(
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
            0x00,  # value
            0x73,
            *bytes.fromhex(addr_hex),
            0x5A,
            0xF1,
            0x00,
        ]
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_depth2_call_chain_skips_hook():
    """A CALL→B CALL→C: B is call-frame (has CALL), C is leaf; hook unused."""
    c_addr = "0x00000000000000000000000000000000000000cc"
    b_addr = "0x00000000000000000000000000000000000000bb"
    # C: SSTORE(1, 7) STOP
    c_code = bytes([0x60, 0x07, 0x60, 0x01, 0x55, 0x00])
    b_code = _call_bytecode(c_addr)
    assert native.evm_bytecode_is_nested_native_eligible(b_code) is False
    assert native.evm_bytecode_is_inline_call_frame_eligible(b_code) is True
    assert native.evm_bytecode_is_nested_native_eligible(c_code) is True

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

    a_code = _call_bytecode(b_addr)
    storage: dict = {}
    ctx = EVMContext(contract_call=hook)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {b_addr: b_code, c_addr: c_code},
        "storages": {b_addr: {}, c_addr: {}},
    }
    evm = EVM(gas_limit=2_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        a_code, 2_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted"), out
    assert hook_calls["n"] == 0, f"expected full native inline, got hook={hook_calls['n']}"
    st = host_ctx["bridge_state"]["storages"][c_addr]
    assert int(st.get(1, st.get("1", 0))) == 7


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_create_in_child_falls_to_hook():
    """Child with CREATE is not call-frame eligible → Python hook."""
    bad = "0x00000000000000000000000000000000000000dd"
    # CREATE opcode 0xF0
    child = bytes([0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0xF0, 0x00])
    assert native.evm_bytecode_is_inline_call_frame_eligible(child) is False
    hook_calls = {"n": 0}

    def hook(target, calldata, value, gas, delegate, static=False, callcode=False):
        hook_calls["n"] += 1
        return {
            "success": True,
            "reverted": False,
            "return_data": b"",
            "gas_used": 5,
            "storage": {},
        }

    parent = _call_bytecode(bad)
    storage: dict = {}
    ctx = EVMContext(contract_call=hook)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {"codes": {bad: child}, "storages": {}}
    evm = EVM(gas_limit=500_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    native.evm_run_nested_host_frame(parent, 500_000, b"", host_ctx, storage, bridge)
    assert hook_calls["n"] == 1


def test_needles_v1375():
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "bytecode_is_inline_call_frame_eligible" in rust
    assert "MAX_INLINE_CALL_DEPTH" in rust
    assert "_abs_inline_depth" in rust
    assert "v1.3.75" in rust or "1.3.75" in rust
