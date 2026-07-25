#!/usr/bin/env python3
"""v1.3.48: nested CALL gas planner (EIP-150 + stipend)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native


def test_gas_planner_python_fallback():
    out = native._evm_plan_nested_call_gas_py(64_000, 50_000, 1, "call")
    assert out["stipend_applied"] is True
    assert out["base_cap"] == 50_000
    assert out["call_gas"] == 52_300
    assert out["native_plan"] is False


def test_gas_planner_table():
    # remaining=64000 → EIP-150 cap = 63000; requested=0 → use cap
    no_value = native.evm_plan_nested_call_gas(64_000, 0, 0, "call")
    assert no_value["stipend_applied"] is False
    assert no_value["call_gas"] == no_value["base_cap"] == 63_000

    with_value = native.evm_plan_nested_call_gas(64_000, 0, 1, "call")
    assert with_value["stipend_applied"] is True
    assert with_value["call_gas"] == min(64_000, 63_000 + 2300)

    static = native.evm_plan_nested_call_gas(64_000, 0, 1, "staticcall")
    assert static["stipend_applied"] is False

    delegate = native.evm_plan_nested_call_gas(64_000, 0, 1, "delegatecall")
    assert delegate["stipend_applied"] is False

    callcode = native.evm_plan_nested_call_gas(64_000, 10_000, 1, "callcode")
    assert callcode["stipend_applied"] is True
    assert callcode["base_cap"] == 10_000
    assert callcode["call_gas"] == 12_300


def test_wiring():
    interp = Path("evm_interpreter.py").read_text(encoding="utf-8")
    assert "evm_plan_nested_call_gas" in interp
    assert "def evm_plan_nested_call_gas" in Path("crypto/native.py").read_text(
        encoding="utf-8"
    )
    assert "fn evm_plan_nested_call_gas" in Path(
        "native/abs_native/src/lib.rs"
    ).read_text(encoding="utf-8")
