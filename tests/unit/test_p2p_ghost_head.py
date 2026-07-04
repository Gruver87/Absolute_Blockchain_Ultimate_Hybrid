#!/usr/bin/env python3
"""P2P reconcile prefers LMD-GHOST canonical head."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from consensus.adapter import ConsensusAdapter
from kernel.event_bus import EventBus
from network.p2p_node import P2PNode
from runtime.config import Config
from storage.database import Database


def _node():
    tmp = tempfile.mkdtemp()
    cfg = Config()
    cfg.db_path = os.path.join(tmp, "p2p.db")
    db = Database(cfg.db_path)
    db.initialize()
    bc = __import__("core.blockchain", fromlist=["Blockchain"]).Blockchain(
        cfg, db, EventBus()
    )
    adapter = ConsensusAdapter(cfg, db, EventBus())
    bc.consensus_adapter = adapter
    p2p = P2PNode(cfg, bc, None)
    p2p.set_consensus(adapter)
    return p2p, adapter


def test_feed_fork_choice_and_ghost_head():
    p2p, adapter = _node()
    parent = "0x" + "aa" * 32
    fork_a = "0x" + "bb" * 32
    fork_b = "0x" + "cc" * 32
    p2p._feed_fork_choice({"hash": parent, "parent_hash": "0x" + "00" * 32, "height": 1})
    p2p._feed_fork_choice({"hash": fork_a, "parent_hash": parent, "height": 2})
    p2p._feed_fork_choice({"hash": fork_b, "parent_hash": parent, "height": 2})
    val = "0x" + "11" * 40
    adapter.add_validator(val, 5000)
    adapter.attest(val, fork_b)
    ghost = p2p._ghost_canonical_head()
    assert ghost == fork_b


def test_consensus_adapter_fallback():
    p2p, adapter = _node()
    p2p._consensus = None
    p2p.blockchain.consensus_adapter = adapter
    assert p2p._consensus_adapter() is adapter
