#!/usr/bin/env python3
"""v1.3.50: nested pure bytecode frame (Priority 22 first slice)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from crypto import native


def test_eligibility_pure_vs_host():
    pure = bytes([0x60, 0x2A, 0x00])  # PUSH1 42 STOP
    assert native.evm_bytecode_is_nested_pure_eligible(pure) is True

    with_call = bytes([0x60, 0x00] * 7 + [0xF1])  # zeros + CALL
    assert native.evm_bytecode_is_nested_pure_eligible(with_call) is False

    with_balance = bytes([0x60, 0x00, 0x31])  # PUSH1 0 BALANCE
    assert native.evm_bytecode_is_nested_pure_eligible(with_balance) is False


def test_nested_pure_frame_return():
    # PUSH1 0x2A, PUSH1 0x00, MSTORE, PUSH1 0x20, PUSH1 0x00, RETURN
    bytecode = bytes([0x60, 0x2A, 0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0xF3])
    assert native.evm_bytecode_is_nested_pure_eligible(bytecode)

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
        },
        {},
    )
    assert out["native_nested_pure"] is True
    assert out["stop_reason"] == "return"
    assert out["success"] is True
    assert out["reverted"] is False
    assert bytes(out["return_data"]) == (b"\x00" * 31 + b"\x2a")


def test_nested_pure_frame_stops_on_call():
    bytecode = bytes([0x60, 0x00] * 7 + [0xF1])
    # Direct call without eligibility gate — should stop at host
    out = native.evm_run_nested_pure_frame(
        bytecode,
        1_000_000,
        b"",
        {"address": 0, "caller": 0, "origin": 0, "value": 0,
         "timestamp": 0, "block_number": 0, "chain_id": 77777},
        {},
    )
    assert out["stop_reason"] == "host"
    assert out.get("host_opcode") in (0xF1, "0xf1", 241) or int(out.get("host_opcode") or 0) == 0xF1


def test_wiring():
    adapter = Path("execution/evm_adapter.py").read_text(encoding="utf-8")
    assert "evm_run_nested_pure_frame" in adapter
    assert "evm_bytecode_is_nested_pure_eligible" in adapter
    assert "fn evm_run_nested_pure_frame" in Path(
        "native/abs_native/src/evm_pure_runner.rs"
    ).read_text(encoding="utf-8") or "evm_run_nested_pure_frame_py" in Path(
        "native/abs_native/src/evm_pure_runner.rs"
    ).read_text(encoding="utf-8")
