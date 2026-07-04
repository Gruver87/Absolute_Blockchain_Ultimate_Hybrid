#!/usr/bin/env python3
"""Live resharding migration flow."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dynamic_sharding import ShardingManager
from storage.database import Database


def test_reshard_discover_and_apply_routing(tmp_path):
    db = Database(str(tmp_path / "reshard.db"))
    db.initialize()
    addr = "0x" + "fa" * 20
    db.set_balance(addr, 100.0)

    sh = ShardingManager(num_shards=2, db=db, mode="routing")
    plan = sh.plan_reshard(4, effective_epoch=1)
    assert plan["to_shards"] == 4
    queued = sh.discover_reshard_migrations()
    assert queued >= 0
    result = sh.process_reshard_migrations(limit=10)
    assert result["processed"] >= 0
    assert sh.apply_reshard() is True
    assert sh.num_shards == 4


def test_distributed_migration_debit_credit(tmp_path):
    db0 = Database(str(tmp_path / "m0.db"))
    db0.initialize()
    db1 = Database(str(tmp_path / "m1.db"))
    db1.initialize()
    addr = "0x" + "be" * 20

    src = ShardingManager(num_shards=2, db=db0, assigned_shard_id=0, mode="distributed")
    dst = ShardingManager(num_shards=2, db=db1, assigned_shard_id=1, mode="distributed")

    row = src.coordinator.queue_address_migration(addr, 0, 1)
    db0.set_balance(addr, 50.0)
    payload = src.coordinator.export_migration_debit(row, db0, src.owns_shard)
    assert payload and payload.get("balance") == 50.0
    assert dst.coordinator.apply_migration_credit(payload, db1, dst.owns_shard) is True
    assert db1.get_balance(addr) == 50.0
    assert db0.get_balance(addr) == 0.0
