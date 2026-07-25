#!/usr/bin/env python3
"""v1.3.55: nested CALL native frame with BALANCE/EXTCODE bridge surface."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native


def test_eligibility_host_vs_bridge():
    pure = bytes([0x60, 0x2A, 0x00])
    assert native.evm_bytecode_is_nested_pure_eligible(pure) is True
    assert native.evm_bytecode_is_nested_native_eligible(pure) is True

    balance = bytes([0x60, 0x00, 0x31, 0x00])  # PUSH1 0 BALANCE STOP
    assert native.evm_bytecode_is_nested_pure_eligible(balance) is False
    assert native.evm_bytecode_is_nested_native_eligible(balance) is True

    call = bytes([0x60, 0x00] * 7 + [0xF1])
    assert native.evm_bytecode_is_nested_native_eligible(call) is False


def test_nested_frame_balance_with_bridge():
    addr_int = 0xAA
    addr = "0x" + format(addr_int, "040x")
    # PUSH20 addr, BALANCE, STOP
    bytecode = bytes([0x73] + [0x00] * 19 + [0xAA, 0x31, 0x00])
    assert native.evm_bytecode_is_nested_native_eligible(bytecode)

    out = native.evm_run_nested_pure_frame(
        bytecode,
        1_000_000,
        b"",
        {
            "address": 1,
            "caller": 2,
            "origin": 2,
            "value": 0,
            "timestamp": 0,
            "block_number": 1,
            "chain_id": 77777,
            "bridge_state": {"balances": {addr: 12345}},
        },
        {},
        allow_bridge=True,
    )
    assert out["stop_reason"] == "halt"
    assert out["success"] is True
    assert out["allow_bridge"] is True
    assert out["stack"] == [12345]


def test_nested_frame_without_bridge_stops_on_balance():
    bytecode = bytes([0x60, 0x00, 0x31])  # PUSH1 0 BALANCE
    out = native.evm_run_nested_pure_frame(
        bytecode,
        1_000_000,
        b"",
        {
            "address": 0,
            "caller": 0,
            "origin": 0,
            "value": 0,
            "timestamp": 0,
            "block_number": 0,
            "chain_id": 77777,
        },
        {},
        allow_bridge=False,
    )
    assert out["stop_reason"] in ("host", "handoff")


def test_wiring():
    adapter = Path("execution/evm_adapter.py").read_text(encoding="utf-8")
    assert "evm_bytecode_is_nested_native_eligible" in adapter
    assert "allow_bridge=True" in adapter
    assert "def evm_bytecode_is_nested_native_eligible" in Path(
        "crypto/native.py"
    ).read_text(encoding="utf-8")
