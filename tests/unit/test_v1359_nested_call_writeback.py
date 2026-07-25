#!/usr/bin/env python3
"""v1.3.59: nested CALL writeback ops planner."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native


def test_writeback_ops_call_with_value():
    out = native.evm_plan_nested_call_writeback(
        "call",
        False,
        "0xcaller",
        "0xtarget",
        10**18,
        True,
        {1: 2},
        [{"topics": ["0x1"], "data": "aa"}],
    )
    assert out["native_writeback"] is True or "ops" in out
    ops = {op["op"]: op for op in out["ops"]}
    assert "set_storage" in ops
    assert ops["set_storage"]["address"] == "0xtarget"
    stor = ops["set_storage"]["storage"]
    assert int(stor.get("1", stor.get(1))) == 2
    assert "transfer_value" in ops
    assert ops["transfer_value"]["from"] == "0xcaller"
    assert ops["transfer_value"]["to"] == "0xtarget"
    assert int(ops["transfer_value"]["value_wei"]) == 10**18
    # call kind does not persist logs in policy
    assert "append_logs" not in ops


def test_writeback_ops_delegatecall_logs():
    out = native.evm_plan_nested_call_writeback(
        "delegatecall",
        False,
        "0xcaller",
        "0xtarget",
        0,
        True,
        {9: 10},
        [{"topics": [], "data": ""}],
    )
    ops = {op["op"]: op for op in out["ops"]}
    assert ops["set_storage"]["address"] == "0xcaller"
    assert "append_logs" in ops
    assert ops["append_logs"]["address"] == "0xcaller"
    assert "transfer_value" not in ops


def test_writeback_empty_on_revert_or_static():
    for kwargs in (
        dict(kind="call", parent_read_only=False, success=False),
        dict(kind="staticcall", parent_read_only=False, success=True),
        dict(kind="call", parent_read_only=True, success=True),
    ):
        out = native.evm_plan_nested_call_writeback(
            kwargs["kind"],
            kwargs["parent_read_only"],
            "0xc",
            "0xt",
            10**18,
            kwargs["success"],
            {1: 1},
            [{"topics": [], "data": "x"}],
        )
        assert out["ops"] == []


def test_python_fallback_matches_shape():
    py = native._evm_plan_nested_call_writeback_py(
        "callcode", False, "0xc", "0xt", 5, True, {3: 4}, [{"topics": ["0xa"], "data": "bb"}]
    )
    assert py["native_writeback"] is False
    ops = {op["op"]: op for op in py["ops"]}
    assert ops["set_storage"]["address"] == "0xc"
    assert "transfer_value" in ops
    assert "append_logs" in ops


def test_adapter_wires_writeback():
    adapter = (ROOT / "execution" / "evm_adapter.py").read_text(encoding="utf-8")
    assert "evm_plan_nested_call_writeback" in adapter
    assert "_apply_nested_writeback_ops" in adapter
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_writeback.rs").read_text(
        encoding="utf-8"
    )
    assert "evm_plan_nested_call_writeback" in rust
