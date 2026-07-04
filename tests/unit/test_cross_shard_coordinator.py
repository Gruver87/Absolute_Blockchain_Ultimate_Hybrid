#!/usr/bin/env python3
"""Cross-shard coordinator quorum and resharding planner."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from consensus.cross_shard_coordinator import CrossShardCoordinator


def test_quorum_requires_both_shards():
    coord = CrossShardCoordinator(4)
    coord.begin("tx1", 0, 2)
    assert coord.quorum_reached("tx1") is False
    assert coord.record_ack("tx1", 0) is False
    assert coord.record_ack("tx1", 2) is True
    assert coord.quorum_reached("tx1") is True


def test_reshard_plan_and_migrations():
    coord = CrossShardCoordinator(2)
    plan = coord.plan_reshard(4, effective_epoch=10)
    assert plan["to_shards"] == 4
    added = coord.discover_migrations(
        [{"address": "0xabc", "balance": 5.0}],
        old_shards=2,
        new_shards=4,
    )
    assert added >= 0
    row = coord.queue_address_migration("0xdef", 1, 3)
    assert row["status"] == "pending"
    assert coord.apply_reshard() is True
    assert coord.num_shards == 4
    assert coord.complete_migration("0xabc") or coord.complete_migration("0xdef")
    assert coord.pending_migrations() == []


def test_validator_quorum_requires_supermajority_per_shard():
    coord = CrossShardCoordinator(4, validator_quorum=2 / 3)
    coord.load_shard_committees({
        0: ["v0a", "v0b", "v0c"],
        2: ["v2a", "v2b", "v2c"],
    })
    coord.begin("tx2", 0, 2)
    assert coord.quorum_reached("tx2") is False
    assert coord.record_validator_ack("tx2", 0, "v0a") is False
    assert coord.record_validator_ack("tx2", 0, "v0b") is False
    assert coord.quorum_reached("tx2") is False
    assert coord.record_validator_ack("tx2", 2, "v2a") is False
    assert coord.record_validator_ack("tx2", 2, "v2b") is True
    assert coord.quorum_reached("tx2") is True
    status = coord.quorum_status("tx2")
    assert status["quorum_reached"] is True
    assert all(row["met"] for row in status["shards"])


def test_load_validators_from_manifest_assigns_shards():
    coord = CrossShardCoordinator(4)
    manifest = {
        "validators": [
            {"node_id": "n0", "shard_id": 0},
            {"node_id": "n1", "shard_id": 0},
            {"node_id": "n2", "shard_id": 1},
        ]
    }
    assert coord.load_validators_from_manifest(manifest) == 3
    assert len(coord.shard_committee(0)) == 2
    assert len(coord.shard_committee(1)) == 1
