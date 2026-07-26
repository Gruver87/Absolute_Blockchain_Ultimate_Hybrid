#!/usr/bin/env python3
"""v1.3.147: typed Rocks account-row ABAR codec + dual-read."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.config import Config

abs_native = pytest.importorskip("abs_native")


def test_needles_v13147():
    assert hasattr(abs_native, "pack_account_row")
    assert hasattr(abs_native, "unpack_account_row")
    assert hasattr(abs_native, "account_blob_to_json")
    assert hasattr(abs_native, "is_account_row_binary")
    rs = (ROOT / "native" / "abs_native" / "src" / "account_row.rs").read_text(
        encoding="utf-8"
    )
    assert "ABAR" in rs
    assert "pack_account_row_value" in rs
    assert "account_blob_to_value" in rs
    store = (ROOT / "storage" / "rocks_store.py").read_text(encoding="utf-8")
    assert "_pack_account_blob" in store
    assert "_loads_account_blob_or_none" in store
    assert "ABAR" in store
    notes = (ROOT / "RELEASE_NOTES_v1.3.147.md").read_text(encoding="utf-8")
    assert "1.3.147-industrial" in notes
    assert Config().node_version.startswith("1.3.147")


def test_pack_unpack_roundtrip():
    row = {
        "address": "0xAbCdef0123456789",
        "balance": 1.25,
        "balance_satoshi": 125_000_000,
        "nonce": 7,
        "code": None,
        "storage": "{}",
    }
    blob = bytes(abs_native.pack_account_row(json.dumps(row)))
    assert abs_native.is_account_row_binary(blob)
    assert blob[:4] == b"ABAR"
    back = json.loads(abs_native.unpack_account_row(blob))
    assert back["address"] == "0xabcdef0123456789"
    assert int(back["nonce"]) == 7
    assert int(back["balance_satoshi"]) == 125_000_000


def test_dual_read_legacy_json():
    row = {
        "address": "0x11",
        "balance": 0.0,
        "balance_satoshi": 0,
        "nonce": 0,
        "code": None,
        "storage": "{}",
    }
    blob = json.dumps(row).encode("utf-8")
    assert not abs_native.is_account_row_binary(blob)
    decoded = json.loads(abs_native.account_blob_to_json(blob))
    assert decoded["address"] == "0x11"


def test_state_root_parity_json_vs_abar():
    row = {
        "address": "0xdead",
        "balance": 2.0,
        "balance_satoshi": 200_000_000,
        "nonce": 1,
        "code": "",
        "storage": "{}",
    }
    json_blob = json.dumps(row, ensure_ascii=False).encode("utf-8")
    abar_blob = bytes(abs_native.pack_account_row(json.dumps(row)))
    root_json = abs_native.state_root_from_account_blobs([json_blob])
    root_abar = abs_native.state_root_from_account_blobs([abar_blob])
    assert root_json == root_abar
