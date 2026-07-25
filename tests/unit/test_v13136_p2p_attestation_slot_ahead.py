#!/usr/bin/env python3
"""v1.3.136: soft attestation slot/target_height ahead ownership gate."""

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


def _node(*, max_ahead: int = 100) -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_max_attestation_slot_ahead = max_ahead
    cfg.p2p_max_peer_height_ahead = max_ahead
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "aa" * 32
    node = P2PNode(cfg, chain, MagicMock())
    vkeys = MagicMock()
    vkeys.verify_attestation.return_value = True
    node.validator_keys = vkeys
    consensus = MagicMock()
    consensus.engine = MagicMock()
    consensus.engine.current_slot = 10
    consensus.attest = MagicMock(return_value=True)
    node._consensus = consensus
    return node


def _att(*, slot: int, height: int) -> dict:
    return {
        "validator": "0x" + ("11" * 20),
        "target_hash": "ab" * 32,
        "target_height": height,
        "slot": slot,
        "signature": "cd" * 32,
        "public_key": "ef" * 33,
    }


def test_needles_v13136():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_attestation_ahead_reject_reason" in p2p
    assert "attestation_slot_ahead" in p2p
    assert "native_attestation_slot_ahead" in p2p
    assert "p2p_max_attestation_slot_ahead" in (
        ROOT / "runtime" / "config.py"
    ).read_text(encoding="utf-8")
    notes = (ROOT / "RELEASE_NOTES_v1.3.136.md").read_text(encoding="utf-8")
    assert "1.3.136-industrial" in notes
    assert Config().node_version == "1.3.136-industrial"
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_attestation_slot_ahead" in metrics
    assert "abs_p2p_attestation_slot_ahead_rejects_total" in metrics


def test_ahead_reason_slot_and_height():
    node = _node(max_ahead=100)
    assert node._attestation_ahead_reject_reason(_att(slot=50, height=50)) == ""
    assert (
        node._attestation_ahead_reject_reason(_att(slot=10_000_000, height=50))
        == "attestation_slot_ahead"
    )
    assert (
        node._attestation_ahead_reject_reason(_att(slot=50, height=10_000_000))
        == "attestation_height_ahead"
    )


@pytest.mark.asyncio
async def test_far_ahead_attestation_not_applied_or_relayed(monkeypatch):
    node = _node(max_ahead=100)
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "att-peer"
    node.peers[peer.peer_id] = peer
    node._relay_attestation = AsyncMock()
    # Bypass native shape gate for unit focus on ahead window.
    monkeypatch.setattr(
        "network.p2p_node.native.validate_p2p_attestation_payload",
        lambda _d: True,
    )
    await node._handle_attestation(peer, _att(slot=10_000_000, height=10_000_000))
    node._consensus.attest.assert_not_called()
    node._relay_attestation.assert_not_called()
    assert node._attestation_slot_ahead_rejects_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_attestation_slot_ahead") is True


@pytest.mark.asyncio
async def test_in_window_attestation_applied(monkeypatch):
    node = _node(max_ahead=100)
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "att-ok"
    node.peers[peer.peer_id] = peer
    node._relay_attestation = AsyncMock()
    monkeypatch.setattr(
        "network.p2p_node.native.validate_p2p_attestation_payload",
        lambda _d: True,
    )
    await node._handle_attestation(peer, _att(slot=50, height=50))
    node._consensus.attest.assert_called_once()
    node._relay_attestation.assert_awaited_once()
    assert node._attestation_slot_ahead_rejects_total == 0
