#!/usr/bin/env python3
"""v1.3.139: refuse height-only catch-up without peer.head."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import P2PNode, PeerConnection
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
    cfg.p2p_catch_up_require_head = True
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "aa" * 32
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13139():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_catch_up_ahead_refuse_reason" in p2p
    assert "catch_up_no_head" in p2p
    assert "native_catch_up_require_head" in p2p
    assert "p2p_catch_up_require_head" in (
        ROOT / "runtime" / "config.py"
    ).read_text(encoding="utf-8")
    notes = (ROOT / "RELEASE_NOTES_v1.3.139.md").read_text(encoding="utf-8")
    assert "1.3.139-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_catch_up_require_head" in metrics
    assert "abs_p2p_catch_up_no_head_refuse_total" in metrics


def test_refuse_reason_height_only():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.height = 110
    peer.head = ""
    assert node._catch_up_ahead_refuse_reason(peer) == "catch_up_no_head"
    peer.head = "ab" * 32
    assert node._catch_up_ahead_refuse_reason(peer) == ""
    peer.height = 10
    peer.head = ""
    assert node._catch_up_ahead_refuse_reason(peer) == ""


def test_schedule_sync_refuses_no_head():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "ahead"
    peer.height = 110
    peer.head = ""
    node.peers[peer.peer_id] = peer
    node._schedule_sync(peer)
    assert node._catch_up_no_head_refuse_total >= 1
    assert peer.peer_id not in node._sync_tasks
    st = node.get_p2p_security_status()
    assert st.get("native_catch_up_require_head") is True


@pytest.mark.asyncio
async def test_sync_with_peer_refuses_no_head():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "sync"
    peer.height = 110
    peer.head = ""
    node.peers[peer.peer_id] = peer
    node._wait_peer_response = AsyncMock()
    await node._sync_with_peer(peer)
    node._wait_peer_response.assert_not_called()
    assert node._catch_up_no_head_refuse_total >= 1
