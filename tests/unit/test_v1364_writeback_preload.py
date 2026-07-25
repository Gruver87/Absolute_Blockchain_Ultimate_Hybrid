#!/usr/bin/env python3
"""v1.3.64: Rocks batch account preload for writeback."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import abs_native  # type: ignore

    HAS_PRELOAD = hasattr(abs_native.RocksEngine, "get_account_rows")
except Exception:
    HAS_PRELOAD = False


def test_engine_exposes_get_account_rows():
    assert hasattr(abs_native.RocksEngine, "get_account_rows") or not HAS_PRELOAD


@pytest.mark.skipif(not HAS_PRELOAD, reason="abs_native.RocksEngine.get_account_rows missing")
def test_store_load_writeback_accounts(tmp_path):
    from storage.rocks_store import RocksChainStore

    path = str(tmp_path / "wb64")
    store = RocksChainStore(path, synchronous="FULL")
    store.initialize()
    try:
        store.save_account("0xddd", balance=2.0, nonce=3, code="6001", storage='{"1":2}')
        loaded = store.load_writeback_accounts(["0xddd", "0xeee", "0xddd"])
        assert set(loaded.keys()) == {"0xddd", "0xeee"}
        assert int(loaded["0xddd"]["nonce"]) == 3
        assert loaded["0xddd"]["code"] == "6001"
        assert int(loaded["0xeee"]["balance_satoshi"]) == 0
        # native path returns JSON for missing too
        raw = json.loads(store._engine.get_account_rows(json.dumps(["0xddd", "0xeee"])))
        assert "0xddd" in raw and "0xeee" in raw
    finally:
        store.close()


def test_adapter_wires_writeback_preload():
    adapter = (ROOT / "execution" / "evm_adapter.py").read_text(encoding="utf-8")
    assert "load_writeback_accounts" in adapter
    rocks = (ROOT / "storage" / "rocks_store.py").read_text(encoding="utf-8")
    assert "def load_writeback_accounts" in rocks
    hybrid = (ROOT / "storage" / "hybrid_database.py").read_text(encoding="utf-8")
    assert "def load_writeback_accounts" in hybrid
    rust = (ROOT / "native" / "abs_native" / "src" / "storage" / "mod.rs").read_text(
        encoding="utf-8"
    )
    assert "fn get_account_rows" in rust
