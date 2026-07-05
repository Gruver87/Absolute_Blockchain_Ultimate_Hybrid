#!/usr/bin/env python3
"""follower_genesis_sync must not mint local genesis on empty follower DB."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from core.blockchain import Blockchain
from kernel.event_bus import EventBus


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
