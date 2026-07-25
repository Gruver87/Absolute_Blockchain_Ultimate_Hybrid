#!/usr/bin/env python3
"""v1.3.134: soft MSG_NEW_BLOCK peer.height ahead ownership gate."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

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
    cfg.p2p_max_peer_height_ahead = 100
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "aa" * 32
    chain.get_block.return_value = None
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13134():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "new_block_height_cap_total" in p2p
    assert "native_new_block_height_cap" in p2p
    assert "v1.3.134" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.134.md").read_text(encoding="utf-8")
    assert "1.3.134-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_new_block_height_cap" in metrics
    assert "abs_p2p_new_block_height_cap_total" in metrics


@pytest.mark.asyncio
async def test_new_block_fantasy_height_capped_no_sync():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "nb-peer"
    peer.height = 5
    peer.head = "aa" * 32
    node.peers[peer.peer_id] = peer
    node._schedule_sync = MagicMock()
    await node._handle_new_block(
        peer,
        {"height": 10_000_000, "hash": "bb" * 32, "transactions": []},
    )
    # local=10, max_ahead=100 → ownership capped at 110; head not updated
    assert peer.height == 110
    assert peer.head == "aa" * 32
    assert node._new_block_height_cap_total >= 1
    node._schedule_sync.assert_not_called()
    st = node.get_p2p_security_status()
    assert st.get("native_new_block_height_cap") is True


@pytest.mark.asyncio
async def test_new_block_within_window_updates_ownership():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "nb-ok"
    peer.height = 5
    peer.head = "aa" * 32
    node.peers[peer.peer_id] = peer
    # height 50 is within local(10)+100; ownership updates before Block.from_dict
    await node._handle_new_block(
        peer,
        {"height": 50, "hash": "cc" * 32, "transactions": []},
    )
    assert peer.height == 50
    assert peer.head == "cc" * 32
    assert node._new_block_height_cap_total == 0
