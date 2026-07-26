#!/usr/bin/env python3
"""v1.3.146: catch-up head↔height bind + local-tip state_root probe."""

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
    cfg.p2p_catch_up_tip_probe = True
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "aa" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13146():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "catch_up_head_height_mismatch" in p2p
    assert "_catch_up_local_tip_probe_refuse_reason" in p2p
    assert "native_catch_up_tip_probe" in p2p
    assert "native_catch_up_head_height_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_catch_up_tip_probe" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.146.md").read_text(encoding="utf-8")
    assert "1.3.146-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_catch_up_tip_probe" in metrics
    assert "abs_p2p_catch_up_tip_probe_refuse_total" in metrics
    assert "abs_p2p_catch_up_head_height_mismatch_total" in metrics


def test_head_height_mismatch_refuse():
    node = _node()
    head = "ab" * 32
    node.get_block = MagicMock(  # type: ignore[method-assign]
        return_value={"hash": head, "height": 50}
    )
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.height = 110
    peer.head = head
    assert node._catch_up_ahead_refuse_reason(peer) == "catch_up_head_height_mismatch"
    peer.height = 50
    # peer.height == local header height but still ahead of our tip (10) — ok for sync gate
    # Actually peer 50 > our 10, and head matches height 50 → allow (empty refuse)
    assert node._catch_up_ahead_refuse_reason(peer) == ""


@pytest.mark.asyncio
async def test_tip_probe_failed_refuse():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "p1"
    peer.height = 20
    peer.head = "cd" * 32
    node.request_peer_state_root = AsyncMock(return_value=None)  # type: ignore
    reason = await node._catch_up_local_tip_probe_refuse_reason(peer)
    assert reason == "catch_up_tip_probe_failed"
    node._bump_catch_up_refuse(reason)
    assert node._catch_up_tip_probe_refuse_total == 1


@pytest.mark.asyncio
async def test_tip_probe_ok_when_response_matches():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "p1"
    peer.height = 20
    peer.head = "cd" * 32
    node.request_peer_state_root = AsyncMock(  # type: ignore
        return_value={"height": 10, "state_root": "aa" * 32, "head_hash": "ee" * 32}
    )
    assert await node._catch_up_local_tip_probe_refuse_reason(peer) == ""
    st = node.get_p2p_security_status()
    assert st.get("native_catch_up_tip_probe") is True
    assert st.get("native_catch_up_head_height_bind") is True
