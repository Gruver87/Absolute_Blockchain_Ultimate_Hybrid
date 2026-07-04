#!/usr/bin/env python3
"""WebSocket eth_subscribe manager tests."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.eth_ws_subscriptions import EthWsSubscriptionManager


def test_subscribe_unsubscribe_roundtrip():
    mgr = EthWsSubscriptionManager()
    sub_id = mgr.subscribe(1, "newHeads")
    assert sub_id.startswith("0x")
    assert mgr.unsubscribe(1, sub_id) is True
    assert mgr.unsubscribe(1, sub_id) is False


def test_new_heads_notification_format():
    mgr = EthWsSubscriptionManager()
    sub_id = mgr.subscribe(7, "newHeads")
    sid = int(sub_id, 16)
    sent = []
    mgr.on_new_block(
        {"height": 5, "hash": "0xabc", "transactions": []},
        lambda b: {"number": "0x5", "hash": b.get("hash")},
        lambda f, bc: [],
        None,
        lambda sid_, payload: sent.append(payload),
    )
    assert sent
    assert sent[0]["method"] == "eth_subscription"
    assert sent[0]["params"]["subscription"] == hex(sid)
    mgr.drop_connection(7)
    assert mgr.get_subscription(sid) is None


def test_pending_tx_subscription():
    mgr = EthWsSubscriptionManager()
    sub_id = mgr.subscribe(2, "newPendingTransactions")
    sid = int(sub_id, 16)
    sent = []
    mgr.on_new_tx({"hash": "0xdead"}, lambda sid_, p: sent.append(p))
    assert sent[0]["params"]["result"] == "0xdead"
    assert mgr.unsubscribe(2, sid) is True
