"""P2P ops error counters surface in security status."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_propagation_log_failure_increments_ops_counter():
    from network.p2p_node import P2PNode

    cfg = MagicMock()
    cfg.node_id = "test-node"
    cfg.bootstrap_peers = []
    cfg.testnet_expected_peers = 0
    cfg.p2p_max_messages_per_sec = 0
    cfg.p2p_ban_seconds = 300
    cfg.p2p_rate_limit_strikes = 5
    cfg.p2p_evict_min_score = 0
    cfg.chain_id = 1
    cfg.p2p_tls_enabled = False

    blockchain = MagicMock()
    mempool = MagicMock()
    node = P2PNode(cfg, blockchain, mempool)

    db = MagicMock()
    db.record_tx_propagation_event.side_effect = RuntimeError("db down")
    node.blockchain.db = db

    node._record_tx_propagation("abc123", "gossip", peer_id="peer1")

    sec = node.get_p2p_security_status()
    assert sec["ops_errors"]["propagation_log_fail"] == 1


def test_status_p2p_hardening_includes_ops_errors():
    from api.http import _status_p2p_hardening_snapshot

    cfg = MagicMock()
    cfg.p2p_max_messages_per_sec = 10
    p2p = MagicMock()
    p2p.get_p2p_security_status.return_value = {
        "tls": {"enabled": True, "ready": True, "identity_binding": "cn", "fail_closed": True},
        "ops_errors": {"propagation_log_fail": 2, "peer_connect_task_fail": 0, "peer_status_send_fail": 1},
    }

    snap = _status_p2p_hardening_snapshot(cfg, p2p)
    assert snap["ops_errors"]["propagation_log_fail"] == 2
    assert snap["ops_errors"]["peer_status_send_fail"] == 1
