#!/usr/bin/env python3
"""Prod fail-closed: refuse tip state_root header rewrite."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.blockchain import Blockchain
from kernel.event_bus import EventBus
from runtime.config import Config
from storage.database import Database


def _chain(deployment: str = "prod", allow_rewrite: bool = False):
    tmp = tempfile.mkdtemp()
    cfg = Config()
    cfg.db_path = os.path.join(tmp, "b.db")
    cfg.deployment_mode = deployment
    cfg.allow_state_root_rewrite = allow_rewrite
    cfg.mining_enabled = False
    cfg.require_wallet_file = False
    db = Database(cfg.db_path)
    db.initialize()
    bus = EventBus()
    bc = Blockchain(cfg, db, bus)
    g = {
        "height": 0,
        "hash": "e" * 64,
        "parent_hash": "0" * 64,
        "timestamp": 0,
        "miner": "0x" + "0" * 40,
        "state_root": "f" * 64,
        "tx_root": "0" * 64,
        "transactions": [],
        "nonce": 0,
        "difficulty": 1,
        "extra_data": "",
        "gas_limit": 0,
        "gas_used": 0,
    }
    if not db.get_block(0):
        db.save_block(g)
    row = {
        "height": 1,
        "hash": "a" * 64,
        "parent_hash": "e" * 64,
        "timestamp": 1,
        "miner": "0x" + "1" * 40,
        "state_root": "c" * 64,
        "tx_root": "d" * 64,
        "transactions": [],
        "nonce": 0,
        "difficulty": 1,
        "extra_data": "",
        "gas_limit": 0,
        "gas_used": 0,
    }
    db.save_block(row)
    return bc


def test_prod_refuses_tip_state_root_rewrite():
    bc = _chain(deployment="prod", allow_rewrite=False)
    assert bc._align_block_state_root_metadata(1, "9" * 64) is False
    tip = bc.db.get_block(1)
    assert tip["state_root"] == "c" * 64


def test_prod_allows_genesis_align():
    bc = _chain(deployment="prod", allow_rewrite=False)
    ok = bc._align_block_state_root_metadata(0, "1" * 64)
    assert ok is True
    g = bc.db.get_block(0)
    assert g["state_root"] == "1" * 64


def test_prod_config_rejects_allow_rewrite_flag():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.allow_state_root_rewrite = True
    cfg.state_root_strict_p2p = True
    errors = cfg.validate()
    assert any("allow_state_root_rewrite" in e for e in errors)
