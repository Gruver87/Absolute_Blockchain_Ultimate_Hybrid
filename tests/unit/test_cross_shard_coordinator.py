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
    row = coord.queue_address_migration("0xabc", 1, 3)
    assert row["status"] == "pending"
    assert coord.apply_reshard() is True
    assert coord.num_shards == 4
    assert coord.complete_migration("0xabc") is True
    assert coord.pending_migrations() == []
