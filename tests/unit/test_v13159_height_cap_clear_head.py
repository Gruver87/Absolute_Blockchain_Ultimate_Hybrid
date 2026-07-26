#!/usr/bin/env python3
"""v1.3.159: height-cap clears fantasy peer.head (status/new_block/handshake)."""

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
    cfg.p2p_max_peer_height_ahead = 100
    cfg.p2p_height_cap_clear_head = True
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "aa" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    chain.get_block = MagicMock(return_value=None)
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13159():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "p2p_height_cap_clear_head" in p2p
    assert "native_height_cap_clear_head" in p2p
    assert "clear fantasy head with capped height" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_height_cap_clear_head" in cfg
    assert "P2P_HEIGHT_CAP_CLEAR_HEAD" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.159.md").read_text(encoding="utf-8")
    assert "1.3.159-industrial" in notes
    assert Config().node_version.startswith("1.3.159")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_height_cap_clear_head" in metrics


@pytest.mark.asyncio
async def test_new_block_cap_clears_head(monkeypatch):
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "cap-nb"
    peer.height = 10
    peer.head = DIGEST
    node.peers[peer.peer_id] = peer
    monkeypatch.setattr(
        "network.p2p_node.native.validate_p2p_block_announce",
        lambda data: {
            "height": int(data.get("height", 0)),
            "hash": data.get("hash", ""),
        },
    )
    # Claim height far above local tip (10) + ahead window (100) ⇒ cap.
    await node._handle_new_block(
        peer,
        {"height": 50_000, "hash": "cd" * 32, "transactions": []},
    )
    assert peer.head == ""
    assert peer.height <= 10 + 100
    assert node._new_block_height_cap_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_height_cap_clear_head") is True


def test_cap_helper_owned_window():
    node = _node()
    owned, capped = node._cap_claimed_peer_height(50_000)
    assert capped is True
    assert owned == 110  # local 10 + ahead 100
