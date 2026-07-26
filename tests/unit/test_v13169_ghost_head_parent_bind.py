#!/usr/bin/env python3
"""v1.3.169: GHOST head parent must match tip-height parent."""

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

GHOST = "ab" * 32
TIP = "aa" * 32
PARENT = "11" * 32
WRONG_PARENT = "22" * 32


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
    cfg.p2p_ghost_head_probe = True
    cfg.p2p_ghost_head_parent_bind = True
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    chain.get_block = MagicMock(return_value={"hash": PARENT, "height": 9})
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value=TIP)  # type: ignore[method-assign]
    node._ghost_canonical_head = MagicMock(return_value=GHOST)  # type: ignore
    return node


def test_needles_v13169():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "ghost_head_parent_mismatch" in p2p
    assert "native_ghost_head_parent_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_ghost_head_parent_bind" in cfg
    assert "P2P_GHOST_HEAD_PARENT_BIND" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.169.md").read_text(encoding="utf-8")
    assert "1.3.169-industrial" in notes
    assert Config().node_version.startswith("1.3.169")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_ghost_head_parent_bind" in metrics


@pytest.mark.asyncio
async def test_ghost_parent_mismatch_refuse():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "gp1"
    peer.height = 10
    peer.head = GHOST
    node.peers[peer.peer_id] = peer
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={"hash": GHOST, "height": 10, "parent_hash": WRONG_PARENT}
    )
    reason = await node._ghost_head_probe_refuse_reason(GHOST, peer)
    assert reason == "ghost_head_parent_mismatch"
    node._bump_ghost_probe_refuse(reason)
    assert node._ghost_head_probe_refuse_total == 1


@pytest.mark.asyncio
async def test_ghost_parent_ok():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "gp2"
    peer.height = 10
    peer.head = GHOST
    node.peers[peer.peer_id] = peer
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={"hash": GHOST, "height": 10, "parent_hash": PARENT}
    )
    assert await node._ghost_head_probe_refuse_reason(GHOST, peer) == ""


@pytest.mark.asyncio
async def test_empty_parent_soft_skips():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "gp3"
    peer.height = 10
    peer.head = GHOST
    node.peers[peer.peer_id] = peer
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={"hash": GHOST, "height": 10, "parent_hash": ""}
    )
    assert await node._ghost_head_probe_refuse_reason(GHOST, peer) == ""


@pytest.mark.asyncio
async def test_reconcile_ghost_aborts_on_parent_mismatch():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "gp4"
    peer.height = 10
    peer.head = GHOST
    node.peers[peer.peer_id] = peer
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={"hash": GHOST, "height": 10, "parent_hash": WRONG_PARENT}
    )
    node._reconcile_to_head_hash = AsyncMock(return_value=True)  # type: ignore
    ok = await node._reconcile_ghost_head(GHOST, peer_hint=peer)
    assert ok is False
    node._reconcile_to_head_hash.assert_not_called()
    assert node._ghost_head_probe_refuse_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_ghost_head_parent_bind") is True
