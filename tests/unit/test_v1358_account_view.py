#!/usr/bin/env python3
"""v1.3.58: native account view decode for nested CALL preload."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from crypto import native


def test_storage_map_from_raw_ok_and_corrupt():
    assert native.account_storage_map_from_raw("{}") == {}
    assert native.account_storage_map_from_raw('{"1": 2, "3": 4}') == {1: 2, 3: 4}
    assert native.account_storage_map_from_raw({5: 6}) == {5: 6}
    assert native.account_storage_map_from_raw("{not-json") is None
    assert native.account_storage_map_from_raw('{"a": 1}') is None


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_account_view_from_blob():
    blob = json.dumps({
        "address": "0x" + "ab" * 20,
        "balance_satoshi": 1000,
        "nonce": 2,
        "code": "6001600055",
        "storage": {"7": 8},
    }).encode()
    view = native.account_view_from_blob(blob)
    assert view["ok"] is True
    assert view["corrupt"] is False
    assert view["native_account_view"] is True
    assert int(view["balance_satoshi"]) == 1000
    assert bytes(view["code_bytes"]).hex() == "6001600055"
    assert {int(k): int(v) for k, v in dict(view["storage"]).items()} == {7: 8}

    bad = native.account_view_from_blob(b"not-json")
    assert bad["ok"] is False
    assert bad["corrupt"] is True


def test_account_view_from_row_python_path():
    row = {
        "address": "0x" + "11" * 20,
        "balance_satoshi": 5,
        "nonce": 1,
        "code": "00",
        "storage": '{"9": 10}',
    }
    view = native.account_view_from_row(row)
    assert view["ok"] is True
    assert view["storage"] == {9: 10}
    assert view["code_bytes"] == b"\x00"

    corrupt = native.account_view_from_row({"storage": "{bad"})
    assert corrupt["corrupt"] is True


def test_source_wires_account_view():
    runner = (ROOT / "native" / "abs_native" / "src" / "account_view.rs").read_text(
        encoding="utf-8"
    )
    assert "account_view_from_blob" in runner
    assert "account_storage_map_from_raw" in runner
    adapter = (ROOT / "execution" / "evm_adapter.py").read_text(encoding="utf-8")
    assert "_account_view" in adapter
    assert "account_storage_map_from_raw" in adapter
    native_py = (ROOT / "crypto" / "native.py").read_text(encoding="utf-8")
    assert "def account_view_from_blob" in native_py
    storage_rs = (ROOT / "native" / "abs_native" / "src" / "storage" / "mod.rs").read_text(
        encoding="utf-8"
    )
    assert "get_account_view" in storage_rs
