#!/usr/bin/env python3
"""v1.3.133: authenticated bootstrap seed identity (TLS fingerprint pins)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import P2PNode, PeerConnection
from network.p2p_tls import bootstrap_pin_map
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
        return b""


def _node(*, bootstrap=None, pins="") -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = list(bootstrap or [])
    cfg.p2p_bootstrap_pins = pins
    chain = MagicMock()
    chain.get_height.return_value = 1
    chain.get_state_root.return_value = "aa" * 32
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13133():
    assert "bootstrap_pin_map" in (
        ROOT / "network" / "p2p_tls.py"
    ).read_text(encoding="utf-8")
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_bootstrap_pin_reject_reason" in p2p
    assert "native_bootstrap_pin_gate" in p2p
    assert "p2p_bootstrap_pins" in (
        ROOT / "runtime" / "config.py"
    ).read_text(encoding="utf-8")
    notes = (ROOT / "RELEASE_NOTES_v1.3.133.md").read_text(encoding="utf-8")
    assert "1.3.133-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_bootstrap_pin_gate" in metrics
    assert "abs_p2p_bootstrap_pin_rejects_total" in metrics


def test_bootstrap_pin_map_parse():
    cfg = Config()
    cfg.p2p_bootstrap_pins = (
        "Seed.Example:5000=abcd" + "ef" * 30 + "@node-a,"
        "127.0.0.1:5001=11" + "22" * 31
    )
    pins = bootstrap_pin_map(cfg)
    assert "seed.example:5000" in pins
    assert pins["seed.example:5000"]["fingerprint"].startswith("abcd")
    assert pins["seed.example:5000"]["node_id"] == "node-a"
    assert pins["127.0.0.1:5001"]["fingerprint"].startswith("11")
    assert "node_id" not in pins["127.0.0.1:5001"]


def test_addr_match_without_pin_still_covers():
    node = _node(bootstrap=["127.0.0.1:5001"], pins="")
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "x"
    peer.host = "127.0.0.1"
    peer.listen_port = 5001
    peer.tls_fingerprint = ""
    node.peers[peer.peer_id] = peer
    assert node._missing_bootstrap_addrs() == []


def test_pin_mismatch_does_not_cover_seed():
    fp_ok = "ab" * 32
    fp_bad = "cd" * 32
    node = _node(
        bootstrap=["seed.example:5000"],
        pins=f"seed.example:5000={fp_ok}",
    )
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "impostor"
    peer.host = "172.16.1.5"
    peer.listen_port = 5000
    peer.dial_target = "seed.example:5000"
    peer.tls_fingerprint = fp_bad
    node.peers[peer.peer_id] = peer
    assert "seed.example:5000" in node._missing_bootstrap_addrs()
    st = node.get_p2p_security_status()
    assert st.get("native_bootstrap_pin_gate") is True
    assert st.get("bootstrap_pins_configured") == 1


def test_pin_match_covers_seed():
    fp = "ab" * 32
    node = _node(
        bootstrap=["seed.example:5000"],
        pins=f"seed.example:5000={fp}@seed-1",
    )
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "seed-1"
    peer.host = "172.16.1.5"
    peer.listen_port = 5000
    peer.dial_target = "seed.example:5000"
    peer.tls_fingerprint = fp
    node.peers[peer.peer_id] = peer
    assert node._missing_bootstrap_addrs() == []


def test_pin_reject_reason_mismatch_and_node_id():
    fp = "ab" * 32
    node = _node(
        bootstrap=["seed.example:5000"],
        pins=f"seed.example:5000={fp}@seed-1",
    )
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.dial_target = "seed.example:5000"
    assert (
        node._bootstrap_pin_reject_reason(peer, "seed-1", "cd" * 32)
        == "bootstrap_pin_mismatch"
    )
    assert (
        node._bootstrap_pin_reject_reason(peer, "wrong", fp)
        == "bootstrap_pin_node_id_mismatch"
    )
    assert node._bootstrap_pin_reject_reason(peer, "seed-1", fp) == ""
