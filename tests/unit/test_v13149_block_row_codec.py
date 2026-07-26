#!/usr/bin/env python3
"""v1.3.149: typed Rocks block-row ABLK codec + dual-read."""

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


def test_needles_v13149():
    assert hasattr(abs_native, "pack_block_row")
    assert hasattr(abs_native, "unpack_block_row")
    assert hasattr(abs_native, "block_blob_to_json")
    assert hasattr(abs_native, "is_block_row_binary")
    rs = (ROOT / "native" / "abs_native" / "src" / "block_row.rs").read_text(
        encoding="utf-8"
    )
    assert "ABLK" in rs
    assert "pack_block_row_value" in rs
    assert "block_blob_to_value" in rs
    store = (ROOT / "storage" / "rocks_store.py").read_text(encoding="utf-8")
    assert "_pack_block_blob" in store
    assert "_loads_block_blob_or_none" in store
    assert "ABLK" in store
    notes = (ROOT / "RELEASE_NOTES_v1.3.149.md").read_text(encoding="utf-8")
    assert "1.3.149-industrial" in notes
    assert Config().node_version.startswith("1.3.149")


def test_pack_unpack_roundtrip():
    row = {
        "height": 7,
        "hash": "0xabc",
        "parent_hash": "0xparent",
        "miner": "0xMiner",
        "timestamp": 100,
        "tx_count": 1,
        "gas_used": 21000,
        "total_burned": 0.5,
        "extra_data": "",
        "state_root": "aa" * 32,
        "tx_root": "bb" * 32,
        "transactions": [
            {"hash": "0x1", "from": "0xa", "to": "0xb", "amount": 1.0}
        ],
        "custom_flag": True,
    }
    blob = bytes(abs_native.pack_block_row(json.dumps(row)))
    assert abs_native.is_block_row_binary(blob)
    assert blob[:4] == b"ABLK"
    back = json.loads(abs_native.unpack_block_row(blob))
    assert int(back["height"]) == 7
    assert back["miner"] == "0xminer"
    assert back["custom_flag"] is True
    assert len(back["transactions"]) == 1
    assert back["state_root"] == "aa" * 32


def test_dual_read_legacy_json():
    row = {
        "height": 1,
        "hash": "0x1",
        "parent_hash": "0x0",
        "miner": "genesis",
        "timestamp": 1,
        "transactions": [],
    }
    blob = json.dumps(row).encode("utf-8")
    assert not abs_native.is_block_row_binary(blob)
    decoded = json.loads(abs_native.block_blob_to_json(blob))
    assert int(decoded["height"]) == 1


def test_proposer_alias_packs_as_miner():
    row = {
        "number": 3,
        "block_hash": "0xhh",
        "parent_hash": "0xpp",
        "proposer": "0xABC",
        "timestamp": 9,
        "transactions": [],
    }
    blob = bytes(abs_native.pack_block_row(json.dumps(row)))
    back = json.loads(abs_native.unpack_block_row(blob))
    assert int(back["height"]) == 3
    assert back["hash"] == "0xhh"
    assert back["miner"] == "0xabc"
