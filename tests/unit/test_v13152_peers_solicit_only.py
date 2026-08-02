#!/usr/bin/env python3
"""v1.3.152: solicit-only MSG_PEERS (discovery pull-armed)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import MSG_PEERS, P2PNode, PeerConnection
from runtime.config import Config


class _FakeWriter:
    def write(self, _data):
        return None

    async def drain(self):
        return None

    def close(self):
        return None

    def get_extra_info(self, _name, default=None):
        return default

    def is_closing(self):
        return False


class _FakeReader:
    async def read(self, _n):
        await asyncio.sleep(0)
        return b""


def _node() -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_peers_solicit_only = True
    cfg.p2p_discovery_allow_private = True
    chain = MagicMock()
    chain.get_height.return_value = 1
    chain.get_state_root.return_value = "aa" * 32
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13152():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "unsolicited_peers" in p2p
    assert "native_peers_solicit_only" in p2p
    assert "_ingest_discovered_peers" in p2p
    assert 'request_ctx={"kind": "peers"}' in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_peers_solicit_only" in cfg
    assert "P2P_PEERS_SOLICIT_ONLY" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.152.md").read_text(encoding="utf-8")
    assert "1.3.152-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_peers_solicit_only" in metrics
    assert "abs_p2p_unsolicited_peers_rejects_total" in metrics


@pytest.mark.asyncio
async def test_unsolicited_peers_struck_no_dial():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "disc"
    node.peers[peer.peer_id] = peer
    before_addrs = list(node._known_addrs)
    scheduled: list[tuple[str, int]] = []
    node._schedule_connect = lambda h, p: scheduled.append((h, p))  # type: ignore[method-assign]
    await node._handle_message(
        peer,
        {"type": MSG_PEERS, "data": ["127.0.0.1:5001", "10.0.0.2:5002"]},
    )
    assert node._unsolicited_peers_rejects_total >= 1
    assert node._known_addrs == before_addrs
    assert scheduled == []
    st = node.get_p2p_security_status()
    assert st.get("native_peers_solicit_only") is True
    assert int(st.get("unsolicited_peers_rejects_total") or 0) >= 1


@pytest.mark.asyncio
async def test_solicited_peers_ingested():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "pull"
    node.peers[peer.peer_id] = peer
    scheduled: list[tuple[str, int]] = []
    node._schedule_connect = lambda h, p: scheduled.append((h, p))  # type: ignore[method-assign]
    # Hostname seeds are remembered; bare IP dials may schedule but must not
    # enter _known_addrs (Wave D — docker bridge IPs dual-dial storm).
    n = node._ingest_discovered_peers(
        peer, ["127.0.0.1:5001", "node2.local:5001"]
    )
    assert n >= 1
    assert "127.0.0.1:5001" not in node._known_addrs
    assert "node2.local:5001" in node._known_addrs
    assert ("node2.local", 5001) in scheduled


@pytest.mark.asyncio
async def test_wrong_waiter_ctx_refuses_peers():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "wrong"
    node.peers[peer.peer_id] = peer
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    node._sync_waiters[peer.peer_id] = ((MSG_PEERS,), fut, {"kind": "mempool"})
    before = int(node._unsolicited_peers_rejects_total or 0)
    await node._handle_message(
        peer,
        {"type": MSG_PEERS, "data": ["127.0.0.1:5001"]},
    )
    assert fut.done()
    assert fut.result() is None
    assert int(node._unsolicited_peers_rejects_total or 0) > before
