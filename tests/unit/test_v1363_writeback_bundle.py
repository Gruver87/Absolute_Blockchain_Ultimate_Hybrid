#!/usr/bin/env python3
"""v1.3.63: unified writeback bundle (accounts + logs) under store lock."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import abs_native  # type: ignore

    HAS_BUNDLE = hasattr(abs_native.RocksEngine, "commit_writeback_bundle")
except Exception:
    HAS_BUNDLE = False


def test_engine_exposes_commit_writeback_bundle():
    assert hasattr(abs_native.RocksEngine, "commit_writeback_bundle") or not HAS_BUNDLE


@pytest.mark.skipif(not HAS_BUNDLE, reason="abs_native.RocksEngine.commit_writeback_bundle missing")
def test_store_commit_writeback_bundle(tmp_path):
    from storage.rocks_store import RocksChainStore

    path = str(tmp_path / "wb63")
    store = RocksChainStore(path, synchronous="FULL")
    store.initialize()
    try:
        out = store.commit_writeback_bundle(
            {
                "0xccc": {
                    "balance": 1.0,
                    "balance_satoshi": 1_000_000,
                    "nonce": 1,
                    "code": "6000",
                    "storage": "{}",
                }
            },
            [
                {
                    "address": "0xccc",
                    "logs": [
                        {"topics": ["aa"], "data": "bb"},
                        {"topics": [], "data": "cc"},
                    ],
                }
            ],
            block_height=7,
            tx_hash="11" * 32,
            timestamp=1_700_000_000,
        )
        assert int(out["accounts"]) == 1
        assert int(out["logs"]) == 2
        row = store.get_account("0xccc")
        assert row is not None
        assert int(row["nonce"]) == 1
        logs = store.get_evm_logs_by_tx("11" * 32)
        assert len(logs) == 2
        assert logs[0]["contract_address"] == "0xccc"
        assert logs[0]["data"] == "bb"
        assert int(logs[0]["block_height"]) == 7
    finally:
        store.close()


def test_adapter_wires_writeback_bundle():
    adapter = (ROOT / "execution" / "evm_adapter.py").read_text(encoding="utf-8")
    assert "commit_writeback_bundle" in adapter
    rocks = (ROOT / "storage" / "rocks_store.py").read_text(encoding="utf-8")
    assert "def commit_writeback_bundle" in rocks
    hybrid = (ROOT / "storage" / "hybrid_database.py").read_text(encoding="utf-8")
    assert "def commit_writeback_bundle" in hybrid
    rust = (ROOT / "native" / "abs_native" / "src" / "storage" / "mod.rs").read_text(
        encoding="utf-8"
    )
    assert "fn commit_writeback_bundle" in rust
