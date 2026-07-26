#!/usr/bin/env python3
"""v1.3.160: NEW_BLOCK contiguous (+1) parent_hash must match local tip."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

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
    cfg.p2p_new_block_contiguous_parent_bind = True
    cfg.p2p_new_block_announce_body_bind = True
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    chain.get_block = MagicMock(return_value=None)
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value=TIP)  # type: ignore[method-assign]
    return node


def test_needles_v13160():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "new_block_contiguous_parent_mismatch" in p2p
    assert "_new_block_contiguous_parent_refuse_reason" in p2p
    assert "native_new_block_contiguous_parent_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_new_block_contiguous_parent_bind" in cfg
    assert "P2P_NEW_BLOCK_CONTIGUOUS_PARENT_BIND" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.160.md").read_text(encoding="utf-8")
    assert "1.3.160-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_new_block_contiguous_parent_bind" in metrics
    assert "abs_p2p_new_block_contiguous_parent_mismatch_total" in metrics


def test_contiguous_parent_refuse_and_ok():
    node = _node()
    bad = SimpleNamespace(hash=DIGEST, height=11, parent_hash=OTHER)
    ok = SimpleNamespace(hash=DIGEST, height=11, parent_hash=TIP)
    far = SimpleNamespace(hash=DIGEST, height=20, parent_hash=OTHER)
    assert (
        node._new_block_contiguous_parent_refuse_reason(bad, 10)
        == "new_block_contiguous_parent_mismatch"
    )
    assert node._new_block_contiguous_parent_refuse_reason(ok, 10) == ""
    assert node._new_block_contiguous_parent_refuse_reason(far, 10) == ""
    st = node.get_p2p_security_status()
    assert st.get("native_new_block_contiguous_parent_bind") is True


@pytest.mark.asyncio
async def test_mismatch_does_not_inflate_tip(monkeypatch):
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "nb-parent"
    peer.height = 5
    peer.head = "ff" * 32
    node.peers[peer.peer_id] = peer
    node._schedule_sync = MagicMock()

    class _Blk:
        def __init__(self):
            self.hash = DIGEST
            self.height = 11
            self.parent_hash = OTHER
            self.transactions = []

        @staticmethod
        def from_dict(_data):
            return _Blk()

    monkeypatch.setattr("core.blockchain.Block", _Blk)
    monkeypatch.setattr(
        "network.p2p_node.native.validate_p2p_block_announce",
        lambda data: {
            "height": int(data.get("height", 0)),
            "hash": data.get("hash", ""),
        },
    )
    await node._handle_new_block(
        peer,
        {"height": 11, "hash": DIGEST, "transactions": []},
    )
    assert peer.height == 5
    assert peer.head == "ff" * 32
    assert node._new_block_contiguous_parent_mismatch_total >= 1
    node._schedule_sync.assert_not_called()
