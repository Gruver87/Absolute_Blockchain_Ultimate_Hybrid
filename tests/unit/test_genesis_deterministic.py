#!/usr/bin/env python3
"""Genesis block must be identical across nodes (P2P parent_hash chain)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from core.blockchain import Blockchain
from kernel.event_bus import EventBus


def test_genesis_hash_matches_for_same_chain_id():
    cfg = Config()
    cfg.chain_id = 778888
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "a.db")
    cfg2 = Config()
    cfg2.chain_id = 778888
    cfg2.db_path = os.path.join(tempfile.mkdtemp(), "b.db")

    db1 = Database(cfg.db_path)
    db1.initialize()
    bc1 = Blockchain(cfg, db1, EventBus())
    g1 = bc1.get_block(0)

    db2 = Database(cfg2.db_path)
    db2.initialize()
    bc2 = Blockchain(cfg2, db2, EventBus())
    g2 = bc2.get_block(0)

    assert g1 is not None and g2 is not None
    assert g1["hash"] == g2["hash"]
    assert g1["timestamp"] == g2["timestamp"]
    assert cfg.resolve_genesis_timestamp() == int(g1["timestamp"])
    live_root = db1.compute_state_root() if hasattr(db1, "compute_state_root") else None
    if live_root is None:
        from execution.state_root import compute_db_state_root
        live_root = compute_db_state_root(db1)
    assert g1.get("state_root") == live_root, (
        f"genesis state_root must match DB after mint: {g1.get('state_root')!r} != {live_root!r}"
    )
