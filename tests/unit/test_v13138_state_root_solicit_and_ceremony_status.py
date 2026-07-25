#!/usr/bin/env python3
"""v1.3.138: solicit-only state_root_response + ceremony_status honesty."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import MSG_STATE_ROOT_RESPONSE, P2PNode, PeerConnection
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
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "aa" * 32
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13138():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "unsolicited_state_root_response" in p2p
    assert "native_state_root_solicit_only" in p2p
    assert (ROOT / "scripts" / "ceremony_status.py").is_file()
    check = (ROOT / "scripts" / "check_all.ps1").read_text(encoding="utf-8")
    assert "ceremony_status" in check
    notes = (ROOT / "RELEASE_NOTES_v1.3.138.md").read_text(encoding="utf-8")
    assert "1.3.138-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_state_root_solicit_only" in metrics
    assert "abs_p2p_unsolicited_state_root_rejects_total" in metrics


@pytest.mark.asyncio
async def test_unsolicited_state_root_struck_no_consistency_flip():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "sr"
    node.peers[peer.peer_id] = peer
    node._state_consistent = True
    await node._handle_message(
        peer,
        {
            "type": MSG_STATE_ROOT_RESPONSE,
            "data": {
                "height": 10,
                "state_root": "bb" * 32,
                "head_hash": "cc" * 32,
            },
        },
    )
    assert node._unsolicited_state_root_rejects_total >= 1
    assert node._state_consistent is True  # must not flip on unsolicited
    st = node.get_p2p_security_status()
    assert st.get("native_state_root_solicit_only") is True


def test_ceremony_status_missing_dir_exits_zero(monkeypatch, tmp_path):
    path = ROOT / "scripts" / "ceremony_status.py"
    spec = importlib.util.spec_from_file_location("ceremony_status", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.delenv("GENESIS_CEREMONY_HASH", raising=False)
    status = mod.ceremony_status(ceremony_dir=str(tmp_path / "nope"))
    assert status["dir_exists"] is False
    assert status["ready"] is False
    assert status["env_pin_set"] is False
