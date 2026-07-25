#!/usr/bin/env python3
"""v1.3.60: CREATE/CREATE2 writeback ops planner."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native


def test_create_writeback_ops_success():
    out = native.evm_plan_create_writeback(
        "0xdeployer",
        "0xchild",
        10**18,
        True,
        "6001600055",
        {1: 2},
    )
    assert out.get("native_create_writeback") is True or "ops" in out
    ops = {op["op"]: op for op in out["ops"]}
    assert "save_account" in ops
    assert ops["save_account"]["address"] == "0xchild"
    assert ops["save_account"]["code"] == "6001600055"
    assert float(ops["save_account"]["balance"]) == 0.0
    assert "transfer_value" in ops
    assert ops["transfer_value"]["from"] == "0xdeployer"
    assert ops["transfer_value"]["to"] == "0xchild"
    assert int(ops["transfer_value"]["value_wei"]) == 10**18


def test_create_writeback_empty_on_revert():
    out = native.evm_plan_create_writeback(
        "0xd", "0xc", 10**18, False, "00", {1: 1}
    )
    assert out["ops"] == []
    assert out["reverted"] is True


def test_create_writeback_no_value_no_transfer():
    out = native.evm_plan_create_writeback(
        "0xd", "0xc", 0, True, "00", {}
    )
    ops = [op["op"] for op in out["ops"]]
    assert ops == ["save_account"]


def test_python_fallback_create_writeback():
    py = native._evm_plan_create_writeback_py(
        "0xd", "0xc", 5, True, "aabb", {3: 4}
    )
    assert py["native_create_writeback"] is False
    assert len(py["ops"]) == 2


def test_adapter_wires_create_writeback():
    adapter = (ROOT / "execution" / "evm_adapter.py").read_text(encoding="utf-8")
    assert "evm_plan_create_writeback" in adapter
    assert 'kind == "save_account"' in adapter or "save_account" in adapter
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_writeback.rs").read_text(
        encoding="utf-8"
    )
    assert "evm_plan_create_writeback" in rust
