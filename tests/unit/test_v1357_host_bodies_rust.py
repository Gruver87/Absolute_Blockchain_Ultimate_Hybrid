#!/usr/bin/env python3
"""v1.3.57: LOG/CALL/CREATE host bodies in Rust via thin hooks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from crypto import native
from evm_interpreter import EVM, EVMContext


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_log_native_without_emit_or_bridge():
    # LOG body must run in Rust with no emit_log and no host_bridge.
    bytecode = bytes([0x60, 0x00, 0x60, 0x00, 0xA0, 0x00])
    table = native.evm_build_jumpdest_table(bytecode)
    seg = native.evm_run_until_halt(
        bytecode,
        0,
        1_000_000,
        0,
        [],
        bytearray(),
        table,
        b"",
        b"",
        {},
        None,
        None,
    )
    assert seg["stop_reason"] == "halt"
    assert not seg.get("reverted")
    assert len(seg.get("logs") or []) == 1


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_call_via_thin_hook_no_runtime_bridge():
    callee = "0x00000000000000000000000000000000000000bb"

    def hook(target, calldata, value, gas, delegate, static=False):
        assert target == callee
        return {
            "success": True,
            "reverted": False,
            "return_data": (99).to_bytes(32, "big"),
            "gas_used": 100,
        }

    ctx = EVMContext(contract_call=hook)
    evm = EVM(gas_limit=500_000, context=ctx)
    addr_hex = callee.replace("0x", "").zfill(40)
    bytecode = bytes([
        0x60, 0x20,
        0x60, 0x00,
        0x60, 0x00,
        0x60, 0x00,
        0x60, 0x00,
        0x73, *bytes.fromhex(addr_hex),
        0x60, 0x64,
        0xF1,
        0x00,
    ])
    result = evm.execute_bytecode(bytecode)
    assert result["reverted"] is False
    assert result["stack"][-1] == 1


def test_source_wires_native_host_bodies():
    runner = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "fn execute_log_native" in runner
    assert "fn execute_call_native" in runner
    assert "fn execute_create_native" in runner
    native_py = (ROOT / "crypto" / "native.py").read_text(encoding="utf-8")
    assert 'hooks["contract_call"]' in native_py
    assert 'hooks["contract_create"]' in native_py
