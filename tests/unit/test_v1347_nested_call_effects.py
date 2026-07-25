#!/usr/bin/env python3
"""v1.3.47: nested CALL effects planner (native policy kernel)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native


def test_planner_symbol_and_python_fallback():
    assert hasattr(native, "evm_plan_nested_call_effects")
    py = native._evm_plan_nested_call_effects_py(
        "call", False, "0xcaller", "0xtarget", 10**18, True
    )
    assert py["persist_value"] is True
    assert py["effective_value_wei"] == 10**18
    assert py["storage_owner"] == "target"
    assert py["native_plan"] is False


def test_planner_table():
    cases = [
        ("call", False, 10**18, True, True, True, False, "target"),
        ("call", False, 0, True, True, False, False, "target"),
        ("callcode", False, 10**18, True, True, True, True, "caller"),
        ("delegatecall", False, 10**18, True, True, False, True, "caller"),
        ("staticcall", False, 10**18, True, False, False, False, "target"),
        ("call", True, 10**18, True, False, False, False, "target"),
        ("call", False, 10**18, False, False, False, False, "target"),
    ]
    for kind, parent_ro, value, success, ps, pv, pl, owner in cases:
        out = native.evm_plan_nested_call_effects(
            kind, parent_ro, "0xc", "0xt", value, success
        )
        assert out["persist_storage"] is ps, (kind, out)
        assert out["persist_value"] is pv, (kind, out)
        assert out["persist_logs"] is pl, (kind, out)
        assert out["storage_owner"] == owner, (kind, out)
        if kind == "staticcall" or parent_ro:
            assert out["nested_read_only"] is True
            assert out["reject_create"] is True


def test_adapter_wires_planner():
    text = Path("execution/evm_adapter.py").read_text(encoding="utf-8")
    assert "evm_plan_nested_call_effects" in text
    assert "def evm_plan_nested_call_effects" in Path("crypto/native.py").read_text(
        encoding="utf-8"
    )
    assert "evm_plan_nested_call_effects" in Path(
        "native/abs_native/src/lib.rs"
    ).read_text(encoding="utf-8")
