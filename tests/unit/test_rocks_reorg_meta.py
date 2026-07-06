#!/usr/bin/env python3
"""Rocks reorg truncate preserves tip state root metadata."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from runtime.config import Config
from storage.rocks_store import RocksChainStore


@pytest.fixture
def store(tmp_path):
    try:
        import abs_native  # noqa: F401
    except ImportError:
        pytest.skip("abs_native not built")
    path = str(tmp_path / "chainstore")
    rs = RocksChainStore(path, synchronous="FULL")
    rs.initialize()
    yield rs
    rs.close()


def _block(height: int, parent: str = "") -> dict:
    h = "0x" + f"{height:064x}"
    return {
        "height": height,
        "number": height,
        "hash": h,
        "parent_hash": parent or ("0x" + "0" * 64 if height == 0 else "0x" + f"{height-1:064x}"),
        "timestamp": 1_700_000_000 + height,
        "state_root": "0x" + f"{height:064x}",
        "transactions": [],
    }


def test_reorg_truncate_restores_tip_meta(store):
    b0 = _block(0)
    b1 = _block(1, b0["hash"])
    b2 = _block(2, b1["hash"])
    store.persist_block_atomic(b0, [])
    store.persist_block_atomic(b1, [])
    store.persist_block_atomic(b2, [])
    assert store.get_chain_tip() == 2

    store.reorg_truncate_above(1)
    assert store.get_chain_tip() == 1
    tip = store.get_last_block()
    assert tip is not None
    live, live_h = store.get_live_state_root_meta()
    assert live_h == 1
    assert live
