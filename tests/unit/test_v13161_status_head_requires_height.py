#!/usr/bin/env python3
"""v1.3.161: STATUS head-only (height<=0) refused when local tip > 0."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import MSG_STATUS, P2PNode, PeerConnection
from runtime.config import Config

DIGEST = "ab" * 32


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


def _node(*, local_h: int = 10) -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_status_head_requires_height = True
    cfg.p2p_status_head_height_bind = True
    chain = MagicMock()
    chain.get_height.return_value = local_h
    chain.get_state_root.return_value = "aa" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13161():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "status_head_without_height" in p2p
    assert "native_status_head_requires_height" in p2p
    assert "p2p_status_head_requires_height" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_status_head_requires_height" in cfg
    assert "P2P_STATUS_HEAD_REQUIRES_HEIGHT" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.161.md").read_text(encoding="utf-8")
    assert "1.3.161-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_status_head_requires_height" in metrics
    assert "abs_p2p_status_head_without_height_total" in metrics


@pytest.mark.asyncio
async def test_head_only_status_refused_when_local_tip(monkeypatch):
    node = _node(local_h=10)
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "st0"
    peer.height = 3
    peer.head = "ff" * 32
    node.peers[peer.peer_id] = peer

    class _Native:
        @staticmethod
        def validate_p2p_status_payload(data):
            return data

        @staticmethod
        def verify_p2p_status_height_head_binding(_data):
            return None

    monkeypatch.setattr("network.p2p_node.native", _Native)
    await node._handle_message(
        peer,
        {"type": MSG_STATUS, "data": {"height": 0, "head_hash": DIGEST}},
    )
    assert peer.head == "ff" * 32  # not overwritten
    assert peer.height == 3
    assert node._status_head_without_height_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_status_head_requires_height") is True


@pytest.mark.asyncio
async def test_head_only_allowed_at_genesis(monkeypatch):
    node = _node(local_h=0)
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "st-gen"
    peer.height = 0
    peer.head = ""
    node.peers[peer.peer_id] = peer

    class _Native:
        @staticmethod
        def validate_p2p_status_payload(data):
            return data

        @staticmethod
        def verify_p2p_status_height_head_binding(_data):
            return None

    monkeypatch.setattr("network.p2p_node.native", _Native)
    await node._handle_message(
        peer,
        {"type": MSG_STATUS, "data": {"height": 0, "head_hash": DIGEST}},
    )
    assert peer.head == DIGEST
    assert node._status_head_without_height_total == 0
