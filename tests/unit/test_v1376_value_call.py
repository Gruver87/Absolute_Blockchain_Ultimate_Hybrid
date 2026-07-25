#!/usr/bin/env python3
"""v1.3.76: value-transfer CALL ownership (fail-closed bridge_state.balances)."""

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


CALLER = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CALLEE = "0x00000000000000000000000000000000000000bb"


def _call_value_bytecode(to_addr: str, value: int) -> bytes:
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
            value & 0xFF,
            0x73,
            *bytes.fromhex(addr_hex),
            0x5A,
            0xF1,
            0x50,  # POP success
            0x00,
        ]
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_value_call_transfers_balances_and_skips_hook():
    child_code = bytes([0x00])  # STOP
    hook_calls = {"n": 0}

    def hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "return_data": b"", "gas_used": 0}

    bytecode = _call_value_bytecode(CALLEE, 5)
    storage: dict = {}
    ctx = EVMContext(contract_call=hook, address=CALLER)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {CALLEE: child_code},
        "storages": {CALLEE: {}},
        "balances": {CALLER: 100, CALLEE: 1},
    }
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 1_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted"), out
    assert hook_calls["n"] == 0
    bal = host_ctx["bridge_state"]["balances"]
    assert int(bal[CALLER]) == 95
    assert int(bal[CALLEE]) == 6


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_insufficient_balance_fails_closed_no_hook():
    child_code = bytes([0x00])
    hook_calls = {"n": 0}

    def hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": True, "reverted": False, "return_data": b"", "gas_used": 1}

    # value=10 but caller only has 3
    bytecode = _call_value_bytecode(CALLEE, 10)
    storage: dict = {}
    ctx = EVMContext(contract_call=hook, address=CALLER)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {CALLEE: child_code},
        "storages": {},
        "balances": {CALLER: 3, CALLEE: 0},
    }
    evm = EVM(gas_limit=500_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 500_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted")
    assert hook_calls["n"] == 0
    bal = host_ctx["bridge_state"]["balances"]
    assert int(bal[CALLER]) == 3
    assert int(bal[CALLEE]) == 0


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_value_call_without_balances_falls_to_hook():
    child_code = bytes([0x00])
    hook_calls = {"n": 0}

    def hook(target, calldata, value, gas, delegate, static=False, callcode=False):
        hook_calls["n"] += 1
        assert int(value) == 2
        return {
            "success": True,
            "reverted": False,
            "return_data": b"",
            "gas_used": 10,
            "storage": {},
        }

    bytecode = _call_value_bytecode(CALLEE, 2)
    storage: dict = {}
    ctx = EVMContext(contract_call=hook, address=CALLER)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {CALLEE: child_code},
        "storages": {},
        # no balances → fall through
    }
    evm = EVM(gas_limit=500_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    native.evm_run_nested_host_frame(bytecode, 500_000, b"", host_ctx, storage, bridge)
    assert hook_calls["n"] == 1


def test_needles_v1376():
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "try_inline_value_transfer" in rust
    assert "InlineValueTransfer" in rust
    assert "v1.3.76" in rust
    assert "native_inline_value_call" in rust
