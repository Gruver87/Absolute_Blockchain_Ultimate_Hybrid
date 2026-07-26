#!/usr/bin/env python3
"""v1.3.72: P2P sync admission + outbound honesty (close v1.3.66 debt)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_needles_v1372():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "p2p_max_sync_inflight" in p2p
    assert "sync admission reject" in p2p
    assert "_bump_outbound_drop" in p2p
    assert "_exempt_rate_ok" in p2p
    assert "outbound max_peers" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_max_sync_inflight" in cfg
    assert "p2p_exempt_messages_per_sec" in cfg
    assert "p2p_send_queue_max" in cfg
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_outbound_drops_total" in metrics
    assert "abs_p2p_sync_admission_rejects_total" in metrics


def test_sync_admission_caps_inflight():
    from network.p2p_node import P2PNode
    from runtime.config import Config

    cfg = Config()
    cfg.p2p_max_sync_inflight = 1
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    bc = MagicMock()
    bc.get_height.return_value = 0
    bc.get_last_block.return_value = None
    mp = MagicMock()
    node = P2PNode(cfg, bc, mp)

    async def _hang(_peer):
        await asyncio.sleep(60)

    node._sync_with_peer_safe = _hang  # type: ignore[method-assign]

    class _Peer:
        peer_id = "peer-a"
        host = "127.0.0.1"
        port = 1
        height = 10
        head = "ab" * 32

    class _PeerB(_Peer):
        peer_id = "peer-b"

    async def _run():
        node._schedule_sync(_Peer())  # type: ignore[arg-type]
        node._schedule_sync(_PeerB())  # type: ignore[arg-type]
        await asyncio.sleep(0.05)
        assert len([t for t in node._sync_tasks.values() if not t.done()]) == 1
        assert node._sync_admission_rejects >= 1
        for t in list(node._sync_tasks.values()):
            t.cancel()
        await asyncio.sleep(0.05)

    asyncio.run(_run())


def test_exempt_secondary_budget():
    from network.p2p_node import P2PNode, MSG_NEW_TX, MSG_STATUS
    from runtime.config import Config

    cfg = Config()
    cfg.p2p_exempt_messages_per_sec = 3
    cfg.p2p_max_messages_per_sec = 500
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    node = P2PNode(cfg, MagicMock(), MagicMock())
    # Force Python path (no native table) for deterministic window math
    node._rl_table = None
    # Sync/housekeeping still on secondary exempt budget (v1.3.143: not new_tx).
    assert node._rate_limit_ok("p1", MSG_STATUS) is True
    assert node._rate_limit_ok("p1", MSG_STATUS) is True
    assert node._rate_limit_ok("p1", MSG_STATUS) is True
    assert node._rate_limit_ok("p1", MSG_STATUS) is False


def test_new_tx_uses_primary_rate_budget():
    """v1.3.143: gossip new_tx is not exempt — hits primary rate limit."""
    from network.p2p_node import P2PNode, MSG_NEW_TX
    from runtime.config import Config

    cfg = Config()
    cfg.p2p_exempt_messages_per_sec = 100
    cfg.p2p_max_messages_per_sec = 2
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    node = P2PNode(cfg, MagicMock(), MagicMock())
    node._rl_table = None
    assert node._rate_limit_ok("p1", MSG_NEW_TX) is True
    assert node._rate_limit_ok("p1", MSG_NEW_TX) is True
    assert node._rate_limit_ok("p1", MSG_NEW_TX) is False


def test_outbound_drop_aggregates():
    from network.p2p_node import P2PNode
    from runtime.config import Config

    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._outbound_drops == 0
    node._bump_outbound_drop()
    node._bump_outbound_drop()
    assert node._outbound_drops == 2
    sec = node.get_p2p_security_status()
    assert sec["outbound_drops"] == 2
    assert sec["max_sync_inflight"] >= 1


def test_metrics_emit_outbound_and_admission():
    from observability.metrics import MetricsCollector

    text = MetricsCollector().render_prometheus(
        node_id="n1",
        apply_isolation={
            "outbound_drops": 4,
            "sync_admission_rejects": 2,
            "max_sync_inflight": 2,
            "sync_tasks": 1,
            "import_offload_total": 0,
        },
    )
    assert "abs_p2p_outbound_drops_total" in text
    assert 'abs_p2p_outbound_drops_total{node_id="n1"} 4' in text
    assert "abs_p2p_sync_admission_rejects_total" in text
    assert 'abs_p2p_sync_admission_rejects_total{node_id="n1"} 2' in text
