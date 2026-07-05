#!/usr/bin/env python3
"""Follower nodes must not re-mint genesis after cloning block #0."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from core.blockchain import Blockchain
from kernel.event_bus import EventBus
from runtime.tokenomics import genesis_balances, resolve_founder_address


def test_apply_genesis_allocation_skips_when_block_zero_exists():
    cfg = Config()
    cfg.chain_id = 778889
    cfg.db_path = os.path.join(tempfile.mkdtemp(), "g.db")
    cfg.miner_address = "0x" + "a" * 40
    cfg.founder_address = cfg.miner_address

    db = Database(cfg.db_path)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())
    assert bc.get_block(0) is not None
    founder_a = resolve_founder_address(cfg.founder_address, cfg.miner_address)
    expected_supply = sum(genesis_balances(founder_a).values())

    cfg2 = Config()
    cfg2.chain_id = cfg.chain_id
    cfg2.db_path = cfg.db_path
    cfg2.miner_address = "0x" + "b" * 40
    cfg2.founder_address = cfg2.miner_address

    db2 = Database(cfg2.db_path)
    db2.initialize()
    bc2 = Blockchain(cfg2, db2, EventBus())

    class _Node:
        def __init__(self):
            self.config = cfg2
            self.db = db2
            self.blockchain = bc2

    from main import NodeOrchestrator

    NodeOrchestrator._apply_genesis_allocation(_Node())
    total = sum(a.get("balance", 0) for a in db2.get_all_accounts())
    assert total == pytest.approx(expected_supply)
