#!/usr/bin/env python3
"""v1.3.151: typed Rocks receipt-row ATXR codec + dual-read."""

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


def test_needles_v13151():
    assert hasattr(abs_native, "pack_receipt_row")
    assert hasattr(abs_native, "unpack_receipt_row")
    assert hasattr(abs_native, "receipt_blob_to_json")
    assert hasattr(abs_native, "is_receipt_row_binary")
    rs = (ROOT / "native" / "abs_native" / "src" / "receipt_row.rs").read_text(
        encoding="utf-8"
    )
    assert "ATXR" in rs
    assert "pack_receipt_row_value" in rs
    assert "receipt_blob_to_value" in rs
    store = (ROOT / "storage" / "rocks_store.py").read_text(encoding="utf-8")
    assert "_pack_receipt_blob" in store
    assert "_loads_receipt_blob_or_none" in store
    assert "ATXR" in store
    notes = (ROOT / "RELEASE_NOTES_v1.3.151.md").read_text(encoding="utf-8")
    assert "1.3.151-industrial" in notes
    assert Config().node_version.startswith("1.3.")


def test_pack_unpack_roundtrip():
    row = {
        "tx_hash": "0xdeadbeef",
        "block_height": 42,
        "block_hash": "0xblock",
        "from_addr": "0xAbC",
        "to_addr": "0xDeF",
        "value": 3.5,
        "fee": 0.002,
        "burned": 0.0,
        "gas_used": 21000,
        "status": 1,
        "created_at": 1_700_000_000,
    }
    blob = bytes(abs_native.pack_receipt_row(json.dumps(row)))
    assert abs_native.is_receipt_row_binary(blob)
    assert blob[:4] == b"ATXR"
    back = json.loads(abs_native.unpack_receipt_row(blob))
    assert back["tx_hash"] == "0xdeadbeef"
    assert back["from_addr"] == "0xabc"
    assert int(back["block_height"]) == 42
    assert int(back["status"]) == 1


def test_dual_read_legacy_json():
    row = {
        "tx_hash": "0x11",
        "block_height": 1,
        "block_hash": "0xb",
        "from_addr": "0x1",
        "to_addr": "0x2",
        "value": 0.0,
        "fee": 0.0,
        "burned": 0.0,
        "gas_used": 21000,
        "status": 0,
        "created_at": 1,
    }
    blob = json.dumps(row).encode("utf-8")
    assert not abs_native.is_receipt_row_binary(blob)
    decoded = json.loads(abs_native.receipt_blob_to_json(blob))
    assert decoded["tx_hash"] == "0x11"


def test_status_fail_closed():
    row = {
        "tx_hash": "0x22",
        "block_height": 2,
        "block_hash": "0xb",
        "from_addr": "0x1",
        "to_addr": "0x2",
        "value": 0.0,
        "fee": 0.0,
        "burned": 0.0,
        "gas_used": 21000,
        "status": "unknown-xyz",
        "created_at": 1,
    }
    blob = bytes(abs_native.pack_receipt_row(json.dumps(row)))
    back = json.loads(abs_native.unpack_receipt_row(blob))
    assert int(back["status"]) == 0
