#!/usr/bin/env python3
"""v1.3.153: NEW_BLOCK announce local head↔height bind."""

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


def _node() -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_max_peer_height_ahead = 100_000
    cfg.p2p_new_block_head_height_bind = True
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "aa" * 32
    chain.get_block.return_value = None
    chain.get_block_by_hash = MagicMock(return_value=None)
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13153():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "new_block_head_height_mismatch" in p2p
    assert "_new_block_head_height_refuse_reason" in p2p
    assert "native_new_block_head_height_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_new_block_head_height_bind" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.153.md").read_text(encoding="utf-8")
    assert "1.3.153-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_new_block_head_height_bind" in metrics
    assert "abs_p2p_new_block_head_height_mismatch_total" in metrics


def test_refuse_reason_mismatch_and_unknown():
    node = _node()
    node.get_block = MagicMock(  # type: ignore[method-assign]
        return_value={"hash": DIGEST, "height": 7}
    )
    assert (
        node._new_block_head_height_refuse_reason(DIGEST, 99)
        == "new_block_head_height_mismatch"
    )
    assert node._new_block_head_height_refuse_reason(DIGEST, 7) == ""
    node.get_block = MagicMock(return_value=None)  # type: ignore[method-assign]
    assert node._new_block_head_height_refuse_reason("ff" * 32, 9) == ""


@pytest.mark.asyncio
async def test_mismatch_does_not_inflate_tip():
    node = _node()
    node.get_block = MagicMock(  # type: ignore[method-assign]
        return_value={"hash": DIGEST, "height": 7}
    )
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "nb-bind"
    peer.height = 5
    peer.head = "aa" * 32
    node.peers[peer.peer_id] = peer
    node._schedule_sync = MagicMock()
    await node._handle_new_block(
        peer,
        {"height": 99, "hash": DIGEST, "transactions": []},
    )
    assert peer.height == 5
    assert peer.head == "aa" * 32
    assert node._new_block_head_height_mismatch_total >= 1
    node._schedule_sync.assert_not_called()
    st = node.get_p2p_security_status()
    assert st.get("native_new_block_head_height_bind") is True
    assert int(st.get("new_block_head_height_mismatch_total") or 0) >= 1
