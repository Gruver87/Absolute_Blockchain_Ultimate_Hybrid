#!/usr/bin/env python3
"""v1.3.182: GET_BLOCKS end clamped to local tip (no DB past tip)."""

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
    cfg.p2p_get_blocks_past_tip_clamp = True
    cfg.sync_batch_size = 100
    chain = MagicMock()
    chain.get_height.return_value = local_h

    def _get_block(h):
        if 0 <= int(h) <= local_h:
            return {"hash": "aa" * 32, "height": int(h)}
        return None

    chain.get_block = MagicMock(side_effect=_get_block)
    chain.get_state_root.return_value = "ee" * 32
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13182():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "get_blocks_past_tip_clamp" in p2p
    assert "_get_blocks_past_tip_clamp_end" in p2p
    assert "native_get_blocks_past_tip_clamp" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_get_blocks_past_tip_clamp" in cfg
    assert "P2P_GET_BLOCKS_PAST_TIP_CLAMP" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.182.md").read_text(encoding="utf-8")
    assert "1.3.182-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_get_blocks_past_tip_clamp" in metrics
    assert "abs_p2p_get_blocks_past_tip_clamp_total" in metrics


def test_clamp_end_past_tip():
    node = _node(local_h=10)
    end, reason = node._get_blocks_past_tip_clamp_end(5, 50)
    assert end == 10
    assert reason == "get_blocks_past_tip_clamp"


def test_no_clamp_when_end_at_or_below_tip():
    node = _node(local_h=10)
    end, reason = node._get_blocks_past_tip_clamp_end(5, 10)
    assert end == 10
    assert reason == ""
    end2, reason2 = node._get_blocks_past_tip_clamp_end(0, 3)
    assert end2 == 3
    assert reason2 == ""


@pytest.mark.asyncio
async def test_handle_clamps_and_skips_db_past_tip():
    node = _node(local_h=10)
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "p1"
    peer.send = AsyncMock(return_value=True)  # type: ignore
    from crypto import native

    orig = native.validate_p2p_get_blocks_payload
    try:
        native.validate_p2p_get_blocks_payload = (  # type: ignore
            lambda _d: {"from_height": 8, "to_height": 60}
        )
        await node._handle_get_blocks(peer, {"from_height": 8, "to_height": 60})
    finally:
        native.validate_p2p_get_blocks_payload = orig  # type: ignore
    peer.send.assert_called()
    args = peer.send.call_args[0]
    assert args[0] == MSG_BLOCKS
    assert len(args[1]) == 3  # heights 8,9,10
    heights_fetched = [c.args[0] for c in node.blockchain.get_block.call_args_list]
    assert max(heights_fetched) == 10
    assert 11 not in heights_fetched
    assert node._get_blocks_past_tip_clamp_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_get_blocks_past_tip_clamp") is True
    assert int(st.get("get_blocks_past_tip_clamp_total", 0) or 0) >= 1
