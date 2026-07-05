#!/usr/bin/env python3
"""Blockchain + Rocks hybrid: no double-burn on add_block path."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import abs_native  # type: ignore

    HAS_ROCKS = hasattr(abs_native, "RocksEngine")
except Exception:
    HAS_ROCKS = False

pytestmark = pytest.mark.skipif(not HAS_ROCKS, reason="abs_native.RocksEngine not built")


def test_hybrid_add_block_does_not_double_apply_burn(tmp_path):
    from runtime.config import Config
    from storage.chain_clone import _clone_rocks_directory
    from storage.factory import open_database
    from kernel.event_bus import EventBus
    from core.blockchain import Blockchain, Transaction

    leader_path = str(tmp_path / "chainstore")
    follower_path = str(tmp_path / "chainstore_b")
    cfg = Config()
    cfg.db_path = leader_path
    cfg.db_engine = "rocksdb"
    cfg.rocksdb_sync = "FULL"
    cfg.burn_address = "0x" + "d" * 40
    db = open_database(cfg)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())

    sender = "0x" + "a1" * 20
    recipient = "0x" + "b2" * 20
    db.set_balance(sender, 100.0)
    db.close()
    _clone_rocks_directory(leader_path, follower_path)

    db = open_database(cfg)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())

    tx = Transaction(from_addr=sender, to_addr=recipient, value=10.0, nonce=0)
    block = bc.create_block([tx], proposer="0x" + "c3" * 20)
    assert bc.add_block(block)

    burn_bal = db.get_balance(cfg.burn_address)
    tip_root = db.get_block(block.height)["state_root"]
    assert tip_root == bc.get_state_root()
    assert burn_bal > 0

    exported = dict(db.get_block(block.height))
    db.close()

    cfg_b = Config()
    cfg_b.db_path = follower_path
    cfg_b.db_engine = "rocksdb"
    cfg_b.rocksdb_sync = "FULL"
    cfg_b.burn_address = cfg.burn_address
    db_b = open_database(cfg_b)
    db_b.initialize()
    bc_b = Blockchain(cfg_b, db_b, EventBus())
    assert bc_b.import_block(exported)
    assert bc_b.get_state_root() == tip_root
    assert db_b.get_balance(cfg.burn_address) == burn_bal
    db_b.close()
