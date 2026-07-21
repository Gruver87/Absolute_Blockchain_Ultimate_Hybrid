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
    assert "peer_sync_fail" in sec["ops_errors"]


def test_peer_tx_reject_increments_ops_counter_and_strikes():
    import asyncio
    from unittest.mock import patch

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
    cfg.gas_price_wei = 0.001

    blockchain = MagicMock()
    blockchain.validate_transaction.return_value = {"valid": False, "error": "bad sig"}
    mempool = MagicMock()
    node = P2PNode(cfg, blockchain, mempool)
    node._strike_peer_sync = MagicMock()

    peer = MagicMock()
    peer.peer_id = "peer-abc"

    with patch("network.p2p_node.native.validate_p2p_wire_tx", return_value=True):
        ok = asyncio.run(
            node._ingest_peer_tx(
                {
                    "from_addr": "0x" + "11" * 20,
                    "to_addr": "0x" + "22" * 20,
                    "value": 1,
                    "nonce": 0,
                    "gas": 21000,
                    "signature": "00" * 64,
                    "public_key": "04" + "aa" * 64,
                    "hash": "ab" * 32,
                },
                source="p2p_gossip",
                peer_id=peer.peer_id,
                peer=peer,
                strike_on_reject=True,
            )
        )
    assert ok is False
    sec = node.get_p2p_security_status()
    assert sec["ops_errors"]["peer_tx_reject"] == 1
    node._strike_peer_sync.assert_called_once()
    assert node._strike_peer_sync.call_args[0][1] == "bad_peer_tx"


def test_import_block_false_increments_ops_counter():
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
    blockchain.import_block.return_value = False
    node = P2PNode(cfg, blockchain, MagicMock())
    assert node.import_block({"hash": "x"}) is False
    assert node.get_p2p_security_status()["ops_errors"]["import_block_fail"] == 1


def test_import_block_fail_increments_ops_counter():
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
    blockchain.import_block.side_effect = RuntimeError("bad block")
    node = P2PNode(cfg, blockchain, MagicMock())
    assert node.import_block({"hash": "x"}) is False
    assert node.get_p2p_security_status()["ops_errors"]["import_block_fail"] == 1


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
    assert snap["attestation_local_fail"] == 0

