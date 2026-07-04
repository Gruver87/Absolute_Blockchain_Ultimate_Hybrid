#!/usr/bin/env python3
"""Integration tests: block state replay on import (multi-node correctness)."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from runtime.config import Config
from storage.database import Database
from kernel.event_bus import EventBus
from core.blockchain import Blockchain, Transaction, Block


@pytest.fixture
def chain(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "replay.db")
    db = Database(cfg.db_path)
    db.initialize()
    bus = EventBus()
    bc = Blockchain(cfg, db, bus)
    return bc


def test_import_block_replays_balances(chain):
    sender = "0x" + "a1" * 20
    recipient = "0x" + "b2" * 20
    chain.db.set_balance(sender, 100.0)

    tx = Transaction(from_addr=sender, to_addr=recipient, value=10.0, nonce=0)
    block = chain.create_block([tx], proposer="0x" + "c3" * 20)
    assert chain.add_block(block)

    assert chain.get_balance(recipient) == 10.0
    assert chain.get_balance(sender) < 100.0


def test_second_node_imports_block_state(tmp_path):
    """Simulate peer: node B imports block JSON from node A with correct balances."""
    db_a = str(tmp_path / "a.db")
    db_b = str(tmp_path / "b.db")
    cfg = Config()
    cfg.db_path = db_a

    node_a = Blockchain(cfg, Database(db_a), EventBus())

    sender = "0x" + "d4" * 20
    recv = "0x" + "e5" * 20
    node_a.db.set_balance(sender, 50.0)
    tx = Transaction(from_addr=sender, to_addr=recv, value=5.0, nonce=0)
    blk = node_a.create_block([tx], proposer="0x" + "f6" * 20)
    node_a.add_block(blk)
    exported = dict(node_a.db.get_block(blk.height))

    cfg_b = Config()
    cfg_b.db_path = db_b
    node_b = Blockchain(cfg_b, Database(db_b), EventBus())
    node_b.db.set_balance(sender, 50.0)

    parent = node_b.get_last_block()
    exported["parent_hash"] = parent["hash"]
    exported["timestamp"] = int(parent["timestamp"]) + 1
    exported["hash"] = Block.from_dict(exported)._compute_hash()

    assert node_b.import_block(exported)
    assert node_b.get_balance(recv) == 5.0
    assert node_b.get_height() == blk.height
