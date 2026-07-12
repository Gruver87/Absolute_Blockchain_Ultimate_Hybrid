#!/usr/bin/env python3
"""Unified consensus path (prod: LMD-GHOST + FinalityEngine only)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from consensus.adapter import ConsensusAdapter
from kernel.event_bus import EventBus
from runtime.config import Config
from storage.database import Database


def _adapter(mode: str = "auto", deployment: str = "dev"):
    tmp = tempfile.mkdtemp()
    cfg = Config()
    cfg.db_path = os.path.join(tmp, "c.db")
    cfg.deployment_mode = deployment
    cfg.consensus_mode = mode
    db = Database(cfg.db_path)
    db.initialize()
    return ConsensusAdapter(cfg, db, EventBus()), cfg


def test_prod_auto_resolves_unified():
    adapter, cfg = _adapter(deployment="prod")
    assert cfg.resolved_consensus_mode() == "unified"
    assert adapter._unified_consensus is True
    assert adapter.casper_engine is None
    assert adapter.beacon_engine is None


def test_dev_auto_keeps_parallel_engines():
    adapter, cfg = _adapter(deployment="dev")
    assert cfg.resolved_consensus_mode() == "parallel"
    assert adapter._unified_consensus is False


def test_unified_on_new_block_skips_parallel_engines():
    adapter, _ = _adapter(mode="unified", deployment="prod")
    assert adapter.casper_engine is None
    assert adapter.beacon_engine is None
    adapter._on_new_block(
        {
            "height": 1,
            "hash": "a" * 64,
            "parent_hash": "b" * 64,
            "miner": "0x" + "1" * 40,
        }
    )


def test_unified_stats_flag():
    adapter, _ = _adapter(mode="unified", deployment="dev")
    stats = adapter.get_stats()
    assert stats["consensus_mode"] == "unified"
    assert stats["unified_consensus_path"] is True
    assert stats["casper_ffg_enabled"] is False
    assert stats["beacon_enabled"] is False
