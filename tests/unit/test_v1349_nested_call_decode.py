#!/usr/bin/env python3
"""v1.3.49: nested CALL frame decode planner."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native


def _call_stack(gas, to, value, ao, asz, ro, rsz):
    # bottom … top(gas)
    return [rsz, ro, asz, ao, value, to, gas]


def _static_stack(gas, to, ao, asz, ro, rsz):
    return [rsz, ro, asz, ao, to, gas]


def test_decode_call_layout():
    stack = _call_stack(100_000, 0xABC, 7, 32, 4, 64, 32)
    out = native.evm_decode_nested_call_frame(0xF1, stack)
    assert out["kind"] == "call"
    assert int(out["gas"]) == 100_000
    assert int(out["to_word"]) == 0xABC
    assert int(out["value"]) == 7
    assert int(out["args_offset"]) == 32
    assert int(out["args_size"]) == 4
    assert int(out["ret_offset"]) == 64
    assert int(out["ret_size"]) == 32
    assert out["stack_consumed"] == 7
    assert out["callcode"] is False


def test_decode_static_and_delegate():
    stack = _static_stack(50_000, 0x11, 0, 0, 0, 0)
    st = native.evm_decode_nested_call_frame(0xFA, stack)
    assert st["kind"] == "staticcall"
    assert int(st["value"]) == 0
    assert st["static"] is True
    assert st["stack_consumed"] == 6

    dg = native.evm_decode_nested_call_frame(0xF4, stack)
    assert dg["kind"] == "delegatecall"
    assert dg["delegate"] is True


def test_decode_with_memory_slice():
    mem = b"\x00" * 32 + b"abcd"
    stack = _call_stack(1, 1, 0, 32, 4, 0, 0)
    out = native.evm_decode_nested_call_frame(0xF1, stack, mem)
    assert out.get("call_data_hex") == "61626364"


def test_wiring():
    bridge = Path("execution/evm_host_bridge.py").read_text(encoding="utf-8")
    assert "evm_decode_nested_call_frame" in bridge
    assert "fn evm_decode_nested_call_frame" in Path(
        "native/abs_native/src/lib.rs"
    ).read_text(encoding="utf-8")
