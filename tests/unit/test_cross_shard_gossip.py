#!/usr/bin/env python3
"""P2P cross-shard gossip routing for validator ACK fan-out."""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from network.p2p_node import P2PNode


def test_schedule_cross_shard_gossip_routes_ack_payload():
    node = P2PNode.__new__(P2PNode)
    node._loop = MagicMock()
    node._running = True
    node.broadcast_shard_migration = MagicMock(return_value=None)
    node.broadcast_cross_shard_ack = MagicMock(return_value=None)
    node.broadcast_cross_shard_tx = MagicMock(return_value=None)

    with patch("asyncio.run_coroutine_threadsafe") as run_sf:
        node._schedule_cross_shard_gossip({"type": "shard_migration", "address": "0x1"})
        node._schedule_cross_shard_gossip({
            "type": "cross_shard_ack",
            "tx_id": "abc",
            "validator_id": "v1",
        })
        node._schedule_cross_shard_gossip({"tx_id": "abc", "amount": 1})

    assert run_sf.call_count == 3
    ack_coro = run_sf.call_args_list[1][0][0]
    assert ack_coro is node.broadcast_cross_shard_ack.return_value
    tx_coro = run_sf.call_args_list[2][0][0]
    assert tx_coro is node.broadcast_cross_shard_tx.return_value
