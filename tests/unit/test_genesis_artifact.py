"""Unit tests for shared ceremony genesis artifact import/export."""

from __future__ import annotations

import json
from pathlib import Path

from sync.genesis_artifact import export_genesis_block, load_genesis_block


def test_export_and_load_genesis_block(tmp_path: Path):
    block = {
        "height": 0,
        "hash": "a" * 64,
        "parent_hash": "0" * 64,
        "state_root": "b" * 64,
        "transactions": [],
    }
    path = tmp_path / "genesis_block.json"
    assert export_genesis_block(
        str(path), block, ceremony_hash="c1", chain_id=778888, founder_address="0xABC"
    )
    loaded = load_genesis_block(str(path))
    assert loaded is not None
    assert loaded["hash"] == "a" * 64
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert raw["ceremony_hash"] == "c1"
    assert raw["chain_id"] == 778888
    assert raw["founder_address"] == "0xabc"


def test_refuse_non_genesis_height(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"height": 1, "hash": "c" * 64}),
        encoding="utf-8",
    )
    assert load_genesis_block(str(path)) is None
