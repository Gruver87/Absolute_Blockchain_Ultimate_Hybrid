#!/usr/bin/env python3
"""v1.3.172: after catch-up to peer.height, tip hash must match peer.head."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import P2PNode, PeerConnection
from runtime.config import Config

PEER_HEAD = "ab" * 32
LOCAL_TIP = "aa" * 32


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


def _node(*, tip_h: int = 10) -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_catch_up_tip_head_bind = True
    chain = MagicMock()
    chain.get_height.return_value = tip_h
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value=LOCAL_TIP)  # type: ignore[method-assign]
    return node


def test_needles_v13172():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "catch_up_tip_head_mismatch" in p2p
    assert "_catch_up_tip_head_refuse_reason" in p2p
    assert "native_catch_up_tip_head_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_catch_up_tip_head_bind" in cfg
    assert "P2P_CATCH_UP_TIP_HEAD_BIND" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.172.md").read_text(encoding="utf-8")
    assert "1.3.172-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_catch_up_tip_head_bind" in metrics
    assert "abs_p2p_catch_up_tip_head_mismatch_total" in metrics


def test_refuse_tip_head_mismatch():
    node = _node(tip_h=10)
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.height = 10
    peer.head = PEER_HEAD
    assert node._catch_up_tip_head_refuse_reason(peer) == "catch_up_tip_head_mismatch"


def test_ok_matching_tip_head():
    node = _node(tip_h=10)
    node.head = MagicMock(return_value=PEER_HEAD)  # type: ignore[method-assign]
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.height = 10
    peer.head = PEER_HEAD
    assert node._catch_up_tip_head_refuse_reason(peer) == ""


def test_height_incomplete_skips():
    node = _node(tip_h=9)
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.height = 10
    peer.head = PEER_HEAD
    assert node._catch_up_tip_head_refuse_reason(peer) == ""


def test_empty_peer_head_skips():
    node = _node(tip_h=10)
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.height = 10
    peer.head = ""
    assert node._catch_up_tip_head_refuse_reason(peer) == ""


def test_bump_and_security_status():
    node = _node(tip_h=10)
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.height = 10
    peer.head = PEER_HEAD
    reason = node._catch_up_tip_head_refuse_reason(peer)
    assert reason == "catch_up_tip_head_mismatch"
    node._bump_catch_up_refuse(reason)
    assert node._catch_up_tip_head_mismatch_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_catch_up_tip_head_bind") is True
    assert int(st.get("catch_up_tip_head_mismatch_total", 0) or 0) >= 1
