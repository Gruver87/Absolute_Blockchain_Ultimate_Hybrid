#!/usr/bin/env python3
"""Wave 32 hardening: real balances, idempotency, feature tiers."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dynamic_sharding import ShardingManager
from storage.database import Database
from features import FeatureFlags, MODULE_TIERS


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "w32.db"), synchronous="NORMAL")
    d.initialize()
    return d


def test_sharding_balance_from_db(db):
    addr = "0x" + "ab" * 20
    db.set_balance(addr, 42.5)
    sh = ShardingManager(num_shards=4, db=db)
    assert sh.get_shard_balance(addr) == 42.5
    st = sh.get_stats()
    assert st["balance_source"] == "chain_state"


def test_cross_shard_validation_rejects_insufficient_balance(db):
    sh = ShardingManager(num_shards=4, db=db)
    sender, recipient = "0x" + "01" * 20, "0x" + "fe" * 20
    if sh.get_shard_for_address(sender) == sh.get_shard_for_address(recipient):
        recipient = "0x" + "ff" * 20
    _, cross_id = sh.add_transaction({
        "from": sender, "to": recipient, "value": 100, "hash": "0xtest",
    })
    assert cross_id
    tx = sh.cross_shard_txs[cross_id]
    assert sh._validate_cross_shard_tx(tx) is False


def test_cross_shard_processing_fails_without_balance_backend():
    sh = ShardingManager(num_shards=4, db=None)
    sender, recipient = "0x" + "11" * 20, "0x" + "22" * 20
    if sh.get_shard_for_address(sender) == sh.get_shard_for_address(recipient):
        recipient = "0x" + "23" * 20
    _, cross_id = sh.add_transaction({
        "from": sender, "to": recipient, "value": 10, "hash": "0xno-db",
    })
    assert cross_id

    sh.process_cross_shard_transactions()

    assert sh.cross_shard_txs[cross_id].status == "failed"
    assert cross_id not in sh.pending_cross_txs


def test_bridge_credit_idempotency(db):
    from bridge.abs_bridge import RustBridge
    from runtime.config import Config
    from kernel.event_bus import EventBus

    cfg = Config()
    cfg.bridge_mode = "simulator"
    cfg.deployment_mode = "dev"
    bus = EventBus()
    br = RustBridge(cfg, db, bus)
    recipient = "0x" + "cc" * 20
    tx = "0xl1incoming123"
    r1 = br.confirm_incoming(tx, recipient, 5.0, "ethereum")
    r2 = br.confirm_incoming(tx, recipient, 5.0, "ethereum")
    assert r1["confirmed"] is True
    assert r2.get("duplicate") is True
    assert db.get_balance(recipient) == 5.0


def test_feature_tiers_mark_dev_only_modules():
    assert MODULE_TIERS["mev"] == "analysis"
    assert MODULE_TIERS["sharding"] == "routing"
    assert MODULE_TIERS["zk"] == "r-and-d"
    flags = FeatureFlags()
    out = flags.to_api_dict(
        {"zk": object(), "sharding": object()},
        config=type("C", (), {"deployment_mode": "prod", "is_production": True})(),
    )
    assert out["zk"]["dev_only"] is True
    assert out["zk"]["enabled"] is False
