#!/usr/bin/env python3
"""v1.3.180: GET_BLOCKS refused when from_height > local tip."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import MSG_BLOCKS, P2PNode, PeerConnection
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


def _node(*, local_h: int = 10) -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_get_blocks_future_refuse = True
    chain = MagicMock()
    chain.get_height.return_value = local_h
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block = MagicMock(return_value={"hash": "aa" * 32, "height": local_h})
    node = P2PNode(cfg, chain, MagicMock())
    return node


def test_needles_v13180():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "get_blocks_future_height" in p2p
    assert "_get_blocks_future_refuse_reason" in p2p
    assert "native_get_blocks_future_refuse" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_get_blocks_future_refuse" in cfg
    assert "P2P_GET_BLOCKS_FUTURE_REFUSE" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.180.md").read_text(encoding="utf-8")
    assert "1.3.180-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_get_blocks_future_refuse" in metrics
    assert "abs_p2p_get_blocks_future_refuse_total" in metrics


def test_refuse_future_from_height():
    node = _node(local_h=10)
    assert node._get_blocks_future_refuse_reason(11) == "get_blocks_future_height"
    assert node._get_blocks_future_refuse_reason(100) == "get_blocks_future_height"


def test_ok_at_or_below_tip():
    node = _node(local_h=10)
    assert node._get_blocks_future_refuse_reason(10) == ""
    assert node._get_blocks_future_refuse_reason(0) == ""


@pytest.mark.asyncio
async def test_handle_sends_empty_on_future():
    node = _node(local_h=10)
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "p1"
    peer.send = AsyncMock(return_value=True)  # type: ignore
    # Bypass native shape gate with already-validated-looking payload via monkeypatch
    from crypto import native

    orig = native.validate_p2p_get_blocks_payload
    try:
        native.validate_p2p_get_blocks_payload = (  # type: ignore
            lambda _d: {"from_height": 50, "to_height": 60}
        )
        await node._handle_get_blocks(peer, {"from_height": 50, "to_height": 60})
    finally:
        native.validate_p2p_get_blocks_payload = orig  # type: ignore
    peer.send.assert_called()
    args = peer.send.call_args[0]
    assert args[0] == MSG_BLOCKS
    assert args[1] == []
    assert node._get_blocks_future_refuse_total >= 1
    node.blockchain.get_block.assert_not_called()
    st = node.get_p2p_security_status()
    assert st.get("native_get_blocks_future_refuse") is True
