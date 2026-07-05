#!/usr/bin/env python3
"""Tests for chain_clone utility."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from storage.chain_clone import clone_chain_data
from storage.database import Database


def test_clone_sqlite_chain(tmp_path):
    src_dir = tmp_path / "node1"
    dst_dir = tmp_path / "node2"
    src_dir.mkdir()
    db = Database(str(src_dir / "blockchain.db"))
    db.initialize()
    db.save_block({"height": 0, "hash": "0" * 64, "miner": "genesis", "transactions": []})
    db.close()

    engine = clone_chain_data(str(src_dir), str(dst_dir))
    assert engine == "sqlite"
    restored = Database(str(dst_dir / "blockchain.db"))
    restored.initialize()
    assert restored.get_chain_tip() == 0
    restored.close()


try:
    import abs_native  # type: ignore

    HAS_ROCKS = hasattr(abs_native, "RocksEngine")
except Exception:
    HAS_ROCKS = False


@pytest.mark.skipif(not HAS_ROCKS, reason="abs_native.RocksEngine not built")
def test_clone_rocks_chainstore(tmp_path):
    from storage.rocks_store import RocksChainStore

    src_dir = tmp_path / "node1"
    dst_dir = tmp_path / "node2"
    src_dir.mkdir()
    rocks = RocksChainStore(str(src_dir / "chainstore"))
    rocks.initialize()
    rocks.save_block({"height": 0, "hash": "0" * 64, "miner": "genesis", "transactions": []})
    rocks.close()

    engine = clone_chain_data(str(src_dir), str(dst_dir))
    assert engine == "rocksdb"
    restored = RocksChainStore(str(dst_dir / "chainstore"))
    restored.initialize()
    assert restored.get_chain_tip() == 0
    restored.close()
