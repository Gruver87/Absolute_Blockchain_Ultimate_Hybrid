#!/usr/bin/env python3
"""Hybrid network path: unified LMD-GHOST + canonical block reorg."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from consensus.adapter import ConsensusAdapter
from kernel.event_bus import EventBus
from runtime.config import Config
from storage.database import Database
from core.blockchain import Blockchain, Block


@pytest.fixture
def hybrid_prod_chain():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.deployment_mode = "prod"
    cfg.consensus_mode = "unified"
    cfg.miner_address = "0x" + "a" * 40
    cfg.founder_address = cfg.miner_address
    db = Database(path)
    db.initialize()
    bus = EventBus()
    bc = Blockchain(cfg, db, bus)
    adapter = ConsensusAdapter(cfg, db, bus)
    bc.consensus_adapter = adapter
    yield cfg, db, bc, adapter
    db.close()
    try:
        os.remove(path)
    except OSError:
        pass


def _fork_block(parent: dict, suffix: str, miner: str) -> Block:
    blk = Block(
        height=parent["height"] + 1,
        parent_hash=parent["hash"],
        miner=miner,
        transactions=[],
        timestamp=int(parent["timestamp"]) + 1,
        extra_data=f"fork-{suffix}",
    )
    return blk


def test_hybrid_ghost_reorg_imports_attested_fork(hybrid_prod_chain):
    cfg, db, bc, adapter = hybrid_prod_chain
    validator = cfg.miner_address
    adapter.add_validator(validator, 10_000)

    parent = bc.create_block([], cfg.miner_address)
    assert bc.add_block(parent)
    parent_dict = db.get_block(parent.height)

    fork_a = _fork_block(parent_dict, "a", cfg.miner_address)
    proposer_b = "0x" + "b" * 40
    fork_b = _fork_block(parent_dict, "b", proposer_b)
    assert bc.add_block(fork_a)

    fd2, path2 = tempfile.mkstemp(suffix=".db")
    os.close(fd2)
    cfg2 = Config()
    cfg2.db_path = path2
    cfg2.deployment_mode = "prod"
    cfg2.consensus_mode = "unified"
    cfg2.miner_address = cfg.miner_address
    cfg2.founder_address = cfg.miner_address
    db2 = Database(path2)
    db2.initialize()
    bc2 = Blockchain(cfg2, db2, EventBus())
    assert bc2.add_block(Block.from_dict(parent_dict))
    assert bc2.add_block(fork_b)
    fork_b_peer = dict(db2.get_block(fork_b.height))
    db2.close()
    os.remove(path2)

    for payload in (
        {
            "hash": parent_dict["hash"],
            "parent_hash": parent_dict["parent_hash"],
            "number": parent_dict["height"],
        },
        {
            "hash": fork_a.hash,
            "parent_hash": fork_a.parent_hash,
            "number": fork_a.height,
        },
        {
            "hash": fork_b_peer["hash"],
            "parent_hash": fork_b_peer["parent_hash"],
            "number": fork_b_peer["height"],
        },
    ):
        adapter.add_block_to_fork_choice(payload)

    adapter.attest(validator, fork_b_peer["hash"])
    assert adapter.get_canonical_head() == fork_b_peer["hash"]

    assert bc.reorg_to_ancestor(parent.height) is True
    assert bc.import_block(fork_b_peer) is True
    tip = db.get_last_block()
    assert tip["height"] == fork_b.height
    assert tip["hash"] == fork_b_peer["hash"]


def test_hybrid_prod_resolves_unified_consensus(hybrid_prod_chain):
    cfg, db, bc, adapter = hybrid_prod_chain
    assert cfg.resolved_consensus_mode() == "unified"
    stats = adapter.get_stats()
    assert stats["unified_consensus_path"] is True
    assert stats["lmd_ghost_enabled"] is True
    assert stats["casper_ffg_enabled"] is False
    assert stats["beacon_enabled"] is False
