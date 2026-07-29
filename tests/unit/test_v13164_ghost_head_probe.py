#!/usr/bin/env python3
"""v1.3.164: GHOST canonical head wire probe before reorg."""

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
OTHER = "cd" * 32
TIP = "aa" * 32


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
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value=TIP)  # type: ignore[method-assign]
    node._ghost_canonical_head = MagicMock(return_value=GHOST)  # type: ignore
    return node


def test_needles_v13164():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "ghost_head_probe_failed" in p2p
    assert "_ghost_head_probe_refuse_reason" in p2p
    assert "_reconcile_ghost_head" in p2p
    assert "native_ghost_head_probe" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_ghost_head_probe" in cfg
    assert "P2P_GHOST_HEAD_PROBE" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.164.md").read_text(encoding="utf-8")
    assert "1.3.164-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_ghost_head_probe" in metrics
    assert "abs_p2p_ghost_head_probe_refuse_total" in metrics


@pytest.mark.asyncio
async def test_ghost_probe_failed_refuse():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "g1"
    peer.height = 10
    peer.head = OTHER
    node.peers[peer.peer_id] = peer
    node._request_block_by_hash = AsyncMock(return_value=None)  # type: ignore
    reason = await node._ghost_head_probe_refuse_reason(GHOST, peer)
    assert reason == "ghost_head_probe_failed"
    node._bump_ghost_probe_refuse(reason)
    assert node._ghost_head_probe_refuse_total == 1


@pytest.mark.asyncio
async def test_ghost_probe_height_mismatch():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "g2"
    peer.height = 10
    peer.head = GHOST
    node.peers[peer.peer_id] = peer
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={"hash": GHOST, "height": 99}
    )
    assert (
        await node._ghost_head_probe_refuse_reason(GHOST, peer)
        == "ghost_head_height_mismatch"
    )


@pytest.mark.asyncio
async def test_reconcile_ghost_aborts_on_probe_fail():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "g3"
    peer.height = 10
    peer.head = OTHER
    node.peers[peer.peer_id] = peer
    node._request_block_by_hash = AsyncMock(return_value=None)  # type: ignore
    node._reorg_and_import_async = AsyncMock(return_value=True)  # type: ignore
    ok = await node._reconcile_ghost_head(GHOST, peer_hint=peer)
    assert ok is False
    node._reorg_and_import_async.assert_not_called()
    assert node._ghost_head_probe_refuse_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_ghost_head_probe") is True


@pytest.mark.asyncio
async def test_ghost_probe_ok_then_reorg():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "g4"
    peer.height = 10
    peer.head = GHOST
    node.peers[peer.peer_id] = peer
    parent = "pp" * 32
    node._tip = TIP

    def _head():
        return node._tip

    node.head = MagicMock(side_effect=_head)  # type: ignore[method-assign]
    node._expected_parent_for_height = MagicMock(return_value=parent)  # type: ignore
    node.get_block = MagicMock(  # type: ignore
        return_value={"hash": TIP, "height": 10, "parent_hash": parent}
    )
    node.blockchain.find_ancestor_height = MagicMock(return_value=9)
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={"hash": GHOST, "height": 10, "parent_hash": parent}
    )

    async def _reorg(_rollback, block):
        node._tip = str(block.get("hash") or GHOST)
        return True

    node._reorg_and_import_async = AsyncMock(side_effect=_reorg)  # type: ignore
    assert await node._reconcile_ghost_head(GHOST, peer_hint=peer) is True
    node._reorg_and_import_async.assert_awaited()
