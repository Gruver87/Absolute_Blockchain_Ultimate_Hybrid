#!/usr/bin/env python3
"""v1.3.135: local state_root consistency + handshake/status tip ownership."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import MSG_STATUS, MSG_STATE_ROOT_RESPONSE, P2PNode, PeerConnection
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


DIGEST = "aa" * 32
OTHER = "bb" * 32
ROOT_OK = "cc" * 32
ROOT_BAD = "dd" * 32


def _node() -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_max_peer_height_ahead = 100
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = ROOT_OK
    chain.get_block.side_effect = lambda h: (
        {"hash": DIGEST, "state_root": ROOT_OK, "height": h}
        if int(h) == 5
        else None
    )
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13135():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    solicit = (ROOT / "sync" / "solicit.py").read_text(encoding="utf-8")
    handlers = (ROOT / "network" / "p2p_dispatch" / "handlers.py").read_text(
        encoding="utf-8"
    )
    surface = p2p + "\n" + solicit + "\n" + handlers
    assert "_state_root_request_ctx" in p2p
    assert "bad_state_root_response_local_root" in surface
    assert "native_handshake_height_cap" in p2p
    assert "native_state_root_local_consistency" in p2p
    assert "_cap_claimed_peer_height" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.135.md").read_text(encoding="utf-8")
    assert "1.3.135-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_handshake_height_cap" in metrics
    assert "abs_p2p_state_root_local_rejects_total" in metrics
    assert "abs_p2p_native_status_capped_head_refuse" in metrics


def test_state_root_request_ctx_tip_and_historical():
    node = _node()
    tip_ctx = node._state_root_request_ctx(10)
    assert tip_ctx["height"] == 10
    assert tip_ctx["expected_state_root"] == ROOT_OK
    hist = node._state_root_request_ctx(5)
    assert hist["expected_head"] == DIGEST
    assert hist["expected_state_root"] == ROOT_OK
    ahead = node._state_root_request_ctx(99)
    assert ahead["expected_head"] == ""
    assert ahead["expected_state_root"] == ""


def test_cap_claimed_peer_height():
    node = _node()
    owned, capped = node._cap_claimed_peer_height(10_000_000)
    assert owned == 110
    assert capped is True
    owned2, capped2 = node._cap_claimed_peer_height(50)
    assert owned2 == 50
    assert capped2 is False


@pytest.mark.asyncio
async def test_status_capped_skips_fantasy_head():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "st"
    peer.height = 5
    peer.head = DIGEST
    node.peers[peer.peer_id] = peer
    await node._handle_message(
        peer,
        {
            "type": MSG_STATUS,
            "data": {"height": 10_000_000, "head_hash": OTHER},
        },
    )
    assert peer.height == 110
    assert peer.head == ""  # v1.3.159: fantasy head cleared on height-cap
    assert node._status_height_cap_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_height_cap_clear_head") is True


@pytest.mark.asyncio
async def test_state_root_local_root_mismatch_struck():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "sr"
    node.peers[peer.peer_id] = peer
    fut = asyncio.get_running_loop().create_future()
    node._sync_waiters[peer.peer_id] = (
        (MSG_STATE_ROOT_RESPONSE,),
        fut,
        {
            "kind": "state_root",
            "height": 10,
            "expected_head": "",
            "expected_state_root": ROOT_OK,
        },
    )
    await node._handle_message(
        peer,
        {
            "type": MSG_STATE_ROOT_RESPONSE,
            "data": {
                "height": 10,
                "state_root": ROOT_BAD,
                "head_hash": DIGEST,
            },
        },
    )
    assert fut.done()
    assert fut.result() is None
    assert node._state_root_local_rejects_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_state_root_local_consistency") is True
    assert st.get("native_handshake_height_cap") is True
