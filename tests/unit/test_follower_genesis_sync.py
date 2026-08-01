#!/usr/bin/env python3
"""follower_genesis_sync must not mint local genesis on empty follower DB."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from core.blockchain import Blockchain
from kernel.event_bus import EventBus

ROOT = Path(__file__).resolve().parents[2]


def test_follower_genesis_sync_skips_local_genesis():
    cfg = Config()
    cfg.chain_id = 778890
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "f.db")
    cfg.follower_genesis_sync = True
    cfg.bootstrap_peers = ["leader:5000"]

    db = Database(cfg.db_path)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())

    assert bc.get_last_block() is None
    assert bc.get_height() == 0


def test_normal_node_still_creates_genesis():
    cfg = Config()
    cfg.chain_id = 778891
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "g.db")
    cfg.follower_genesis_sync = False

    db = Database(cfg.db_path)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())

    assert bc.get_last_block() is not None
    assert bc.get_block(0) is not None


def test_follower_skips_local_genesis_allocation_until_import():
    """Source gate: followers must not credit local wallet founder before block #0."""
    main_py = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "follower_genesis_sync: defer genesis allocation" in main_py
    assert "self._pin_chain_founder_address()" in main_py
    bc_py = (ROOT / "core" / "blockchain.py").read_text(encoding="utf-8")
    assert "_seed_follower_genesis_balances" in bc_py
