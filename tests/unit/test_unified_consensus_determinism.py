#!/usr/bin/env python3
"""Unified consensus determinism across independent node adapters."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from consensus.adapter import ConsensusAdapter
from kernel.event_bus import EventBus
from runtime.config import Config
from storage.database import Database


def _unified_adapter(tmp: str, node_id: str) -> ConsensusAdapter:
    cfg = Config()
    cfg.db_path = os.path.join(tmp, f"{node_id}.db")
    cfg.deployment_mode = "prod"
    cfg.consensus_mode = "unified"
    db = Database(cfg.db_path)
    db.initialize()
    return ConsensusAdapter(cfg, db, EventBus())


def test_unified_ghost_head_matches_on_two_nodes():
    tmp = tempfile.mkdtemp()
    a = _unified_adapter(tmp, "n1")
    b = _unified_adapter(tmp, "n2")
    validator = "0x" + "aa" * 40
    a.add_validator(validator, 10_000)
    b.add_validator(validator, 10_000)

    parent = "0x" + "11" * 32
    fork_low = "0x" + "22" * 32
    fork_high = "0x" + "33" * 32
    blocks = [
        {"hash": parent, "parent_hash": "0x" + "00" * 32, "height": 1},
        {"hash": fork_low, "parent_hash": parent, "height": 2},
        {"hash": fork_high, "parent_hash": parent, "height": 2},
    ]
    for block in blocks:
        payload = {
            "hash": block["hash"],
            "parent_hash": block["parent_hash"],
            "number": block["height"],
        }
        a.add_block_to_fork_choice(payload)
        b.add_block_to_fork_choice(payload)

    a.attest(validator, fork_high)
    b.attest(validator, fork_high)

    head_a = a.get_canonical_head()
    head_b = b.get_canonical_head()
    assert head_a == head_b == fork_high
    assert a.get_stats()["consensus_mode"] == "unified"
    assert b.get_stats()["unified_consensus_path"] is True
