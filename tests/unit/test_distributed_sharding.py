#!/usr/bin/env python3
"""Distributed sharding: per-node shard ownership + cross-shard credit."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dynamic_sharding import ShardingManager
from storage.database import Database


def _cross_shard_pair(num_shards=4):
    for i in range(200):
        a = f"0x{i:040x}"
        b = f"0x{(i + num_shards * 17):040x}"
        sh = ShardingManager(num_shards=num_shards)
        if sh.get_shard_for_address(a) != sh.get_shard_for_address(b):
            return a, b, sh.get_shard_for_address(a), sh.get_shard_for_address(b)
    raise RuntimeError("no cross-shard pair")


def test_distributed_cross_shard_two_dbs(tmp_path):
    db0 = Database(str(tmp_path / "s0.db"))
    db0.initialize()
    db1 = Database(str(tmp_path / "s1.db"))
    db1.initialize()

    sender, recipient, from_shard, to_shard = _cross_shard_pair(2)
    db0.set_balance(sender, 100.0)

    src = ShardingManager(
        num_shards=2,
        db=db0,
        assigned_shard_id=from_shard,
        node_id="shard-src",
        mode="distributed",
    )
    dst = ShardingManager(
        num_shards=2,
        db=db1,
        assigned_shard_id=to_shard,
        node_id="shard-dst",
        mode="distributed",
    )

    _, tx_id = src.add_transaction({"from": sender, "to": recipient, "value": 25.0, "nonce": 0})
    assert tx_id
    assert src.cross_shard_txs[tx_id].status == "debited"
    assert db0.get_balance(sender) == 75.0
    assert db1.get_balance(recipient) == 0.0

    payload = src.export_cross_shard_payload(tx_id)
    assert dst.receive_cross_shard_credit(payload) is True
    assert db1.get_balance(recipient) == 25.0

    ack = {"tx_id": tx_id, "to_shard": to_shard, "status": "confirmed"}
    assert src.receive_cross_shard_ack(ack) is True
    assert src.cross_shard_txs[tx_id].status == "confirmed"


def test_distributed_rejects_foreign_sender(tmp_path):
    db = Database(str(tmp_path / "s.db"))
    db.initialize()
    sender, recipient, from_shard, to_shard = _cross_shard_pair(2)
    wrong = ShardingManager(
        num_shards=2,
        db=db,
        assigned_shard_id=to_shard,
        node_id="wrong-shard",
        mode="distributed",
    )
    with pytest.raises(ValueError, match="foreign_shard_sender"):
        wrong.add_transaction({"from": sender, "to": recipient, "value": 1.0})


def test_routing_mode_settles_on_one_db(tmp_path):
    db = Database(str(tmp_path / "route.db"))
    db.initialize()
    sender, recipient, _, _ = _cross_shard_pair(4)
    db.set_balance(sender, 50.0)
    sh = ShardingManager(num_shards=4, db=db, mode="routing")
    _, tx_id = sh.add_transaction({"from": sender, "to": recipient, "value": 10.0})
    assert tx_id
    assert sh.cross_shard_txs[tx_id].status == "confirmed"
    assert db.get_balance(sender) == 40.0
    assert db.get_balance(recipient) == 10.0
