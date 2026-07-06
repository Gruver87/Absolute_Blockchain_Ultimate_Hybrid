#!/usr/bin/env python3
"""Rocks reorg truncate preserves tip state root metadata."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from runtime.config import Config
from runtime.tokenomics import genesis_balances
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


def _block(height: int, parent: str = "", *, state_root: str = "", miner: str = "") -> dict:
    h = "0x" + f"{height:064x}"
    return {
        "height": height,
        "number": height,
        "hash": h,
        "parent_hash": parent or ("0x" + "0" * 64 if height == 0 else "0x" + f"{height-1:064x}"),
        "timestamp": 1_700_000_000 + height,
        "state_root": state_root,
        "miner": miner or ("0x" + "a" * 40),
        "transactions": [],
    }


def test_reorg_truncate_restores_tip_meta(store):
    b0 = _block(0, state_root="0x" + "0" * 64)
    b1 = _block(1, b0["hash"], state_root="0x" + "1" * 64)
    b2 = _block(2, b1["hash"], state_root="0x" + "2" * 64)
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
    assert live == "0x" + "1" * 64


def test_persist_block_atomic_keeps_compute_root_in_sync_with_live_meta(store):
    founder = "0x" + "f" * 40
    for addr, amount in genesis_balances(founder).items():
        store.set_balance(addr, float(amount))

    roots: list[str] = []
    parent = "0x" + "0" * 64
    for height in range(1, 4):
        store.update_balance("0x" + f"{height:040x}", float(height))
        root = store.compute_state_root()
        block = _block(height, parent, state_root=root, miner=founder)
        assert store.persist_block_atomic(block, [])
        live_root, live_h = store.get_live_state_root_meta()
        assert live_h == height
        assert live_root == root
        assert store.compute_state_root() == root
        roots.append(root)
        parent = block["hash"]

    store.reorg_truncate_above(1)
    tip = store.get_last_block()
    assert tip is not None
    live_root, live_h = store.get_live_state_root_meta()
    assert live_h == 1
    assert live_root == roots[0]
    assert str(tip.get("state_root", "")) == roots[0]
