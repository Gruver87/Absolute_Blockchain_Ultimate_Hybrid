#!/usr/bin/env python3
"""v1.3.79: CALLCODE value via fail-closed bridge_state.balances."""

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
CODE_ADDR = "0x00000000000000000000000000000000000000cc"


def _callcode_value_bytecode(code_addr: str, value: int) -> bytes:
    """CALLCODE (0xF2): gas, addr, value, args*, ret* — runs foreign code in self context."""
    addr_hex = code_addr.replace("0x", "").zfill(40)
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
            0xF2,  # CALLCODE
            0x50,  # POP success
            0x00,
        ]
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_callcode_value_succeeds_without_hook_balances_unchanged():
    # CALLCODE credits self: net balance no-op when balances map present.
    child_code = bytes([0x00])  # STOP
    hook_calls = {"n": 0}

    def hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "return_data": b"", "gas_used": 0}

    bytecode = _callcode_value_bytecode(CODE_ADDR, 5)
    storage: dict = {}
    ctx = EVMContext(contract_call=hook, address=CALLER)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {CODE_ADDR: child_code},
        "storages": {},
        "balances": {CALLER: 100, CODE_ADDR: 7},
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
    assert int(bal[CALLER]) == 100
    assert int(bal[CODE_ADDR]) == 7


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_callcode_insufficient_fails_closed():
    child_code = bytes([0x00])
    hook_calls = {"n": 0}

    def hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": True, "reverted": False, "return_data": b"", "gas_used": 1}

    bytecode = _callcode_value_bytecode(CODE_ADDR, 50)
    storage: dict = {}
    ctx = EVMContext(contract_call=hook, address=CALLER)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {CODE_ADDR: child_code},
        "storages": {},
        "balances": {CALLER: 10, CODE_ADDR: 0},
    }
    evm = EVM(gas_limit=500_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 500_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted")
    assert hook_calls["n"] == 0
    assert int(host_ctx["bridge_state"]["balances"][CALLER]) == 10


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_callcode_value_without_balances_falls_to_hook():
    child_code = bytes([0x00])
    hook_calls = {"n": 0}

    def hook(target, calldata, value, gas, delegate, static=False, callcode=False):
        hook_calls["n"] += 1
        assert callcode is True
        assert int(value) == 3
        return {
            "success": True,
            "reverted": False,
            "return_data": b"",
            "gas_used": 10,
            "storage": {},
        }

    bytecode = _callcode_value_bytecode(CODE_ADDR, 3)
    storage: dict = {}
    ctx = EVMContext(contract_call=hook, address=CALLER)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {CODE_ADDR: child_code},
        "storages": {},
        # no balances → fall through
    }
    evm = EVM(gas_limit=500_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    native.evm_run_nested_host_frame(bytecode, 500_000, b"", host_ctx, storage, bridge)
    assert hook_calls["n"] == 1


def test_needles_v1379():
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "native_inline_callcode_value" in rust
    assert "v1.3.79" in rust
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "1.3.79-industrial" in cfg
