#!/usr/bin/env python3
"""v1.3.157: catch-up contiguous (+1) peer.head parent_hash bind."""

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

DIGEST = "ab" * 32
TIP = "aa" * 32
OTHER = "cd" * 32


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
    cfg.p2p_catch_up_peer_head_probe = True
    cfg.p2p_catch_up_peer_head_parent_bind = True
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value=TIP)  # type: ignore[method-assign]
    return node


def test_needles_v13157():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "catch_up_peer_head_parent_mismatch" in p2p
    assert "p2p_catch_up_peer_head_parent_bind" in p2p
    assert "native_catch_up_peer_head_parent_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_catch_up_peer_head_parent_bind" in cfg
    assert "P2P_CATCH_UP_PEER_HEAD_PARENT_BIND" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.157.md").read_text(encoding="utf-8")
    assert "1.3.157-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_catch_up_peer_head_parent_bind" in metrics


@pytest.mark.asyncio
async def test_parent_mismatch_on_contiguous():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "p1"
    peer.height = 11  # local+1
    peer.head = DIGEST
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={"hash": DIGEST, "height": 11, "parent_hash": OTHER}
    )
    reason = await node._catch_up_peer_head_probe_refuse_reason(peer)
    assert reason == "catch_up_peer_head_parent_mismatch"
    node._bump_catch_up_refuse(reason)
    assert node._catch_up_peer_head_probe_refuse_total == 1


@pytest.mark.asyncio
async def test_parent_ok_on_contiguous():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "p1"
    peer.height = 11
    peer.head = DIGEST
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={"hash": DIGEST, "height": 11, "parent_hash": TIP}
    )
    assert await node._catch_up_peer_head_probe_refuse_reason(peer) == ""
    st = node.get_p2p_security_status()
    assert st.get("native_catch_up_peer_head_parent_bind") is True


@pytest.mark.asyncio
async def test_parent_bind_skipped_when_gap_gt_one():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "p1"
    peer.height = 20  # gap > 1
    peer.head = DIGEST
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={"hash": DIGEST, "height": 20, "parent_hash": OTHER}
    )
    assert await node._catch_up_peer_head_probe_refuse_reason(peer) == ""
