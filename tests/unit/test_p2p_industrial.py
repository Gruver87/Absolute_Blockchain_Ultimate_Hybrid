#!/usr/bin/env python3
"""Industrial P2P hardening: wire limits, topology scores, auto prod-mesh detect."""

import asyncio
import importlib.util
import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from network.p2p_node import DEFAULT_MAX_P2P_LINE_BYTES, PeerConnection, _max_p2p_line_bytes
from runtime.config import Config


class _FakeReader:
    def __init__(self, payload: bytes):
        self._payload = payload

    async def readline(self):
        return self._payload


class _FakeWriter:
    def get_extra_info(self, key, default=None):
        if key == "peername":
            return ("127.0.0.1", 5001)
        return default

    def write(self, _data):
        pass

    async def drain(self):
        pass

    def close(self):
        pass


@pytest.mark.asyncio
async def test_recv_rejects_oversized_line():
    peer = PeerConnection(_FakeReader(b"x" * 5000), _FakeWriter())
    cfg = Config()
    cfg.p2p_max_message_bytes = 1024
    msg = await peer.recv(cfg)
    assert msg is None


@pytest.mark.asyncio
async def test_recv_accepts_valid_json_line():
    payload = json.dumps({"type": "ping", "data": {}}).encode() + b"\n"
    peer = PeerConnection(_FakeReader(payload), _FakeWriter())
    msg = await peer.recv(Config())
    assert msg is not None
    assert msg["type"] == "ping"


def test_max_p2p_line_bytes_clamps_config():
    cfg = Config()
    cfg.p2p_max_message_bytes = 100
    assert _max_p2p_line_bytes(cfg) == 4096
    cfg.p2p_max_message_bytes = 999999999
    assert _max_p2p_line_bytes(cfg) == 16 * 1024 * 1024
    assert _max_p2p_line_bytes(Config()) == DEFAULT_MAX_P2P_LINE_BYTES


def _load_verify_p2p():
    path = os.path.join(ROOT, "scripts", "verify_p2p_ci.py")
    spec = importlib.util.spec_from_file_location("verify_p2p_ci", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_verify_p2p_auto_prefers_devnet_over_prod_mesh(monkeypatch):
    mod = _load_verify_p2p()

    def fake_probe(url):
        return url in (
            mod.PROD_MESH_URL1,
            mod.PROD_MESH_URL2,
            mod.PROD_MESH_URL3,
            mod.DEVNET_URL1,
            mod.DEVNET_URL2,
        )

    monkeypatch.setattr(mod, "_probe_health", fake_probe)
    monkeypatch.setattr(mod, "verify_pair", lambda *a, **k: 0)
    monkeypatch.setattr(sys, "argv", ["verify_p2p_ci.py", "--mode", "auto", "--prefer-devnet"])
    assert mod.main() == 0


def test_verify_p2p_auto_detects_prod_mesh_with_prefer_flag(monkeypatch):
    mod = _load_verify_p2p()

    def fake_probe(url):
        return url in (
            mod.PROD_MESH_URL1,
            mod.PROD_MESH_URL2,
            mod.PROD_MESH_URL3,
        )

    monkeypatch.setattr(mod, "_probe_health", fake_probe)
    monkeypatch.setattr(mod, "verify_triple", lambda *a, **k: 0)
    monkeypatch.setattr(mod, "verify_prod_consensus_mesh3", lambda *a, **k: 0)
    monkeypatch.setattr(mod, "verify_prod_post_checks", lambda *a, **k: 0)
    monkeypatch.setattr(
        sys,
        "argv",
        ["verify_p2p_ci.py", "--mode", "auto", "--prefer-prod-mesh"],
    )
    assert mod.main() == 0


def test_consistency_harness_uses_long_timeout_on_prod_ports(monkeypatch):
    mod = _load_verify_p2p()
    calls = []

    def fake_api(url, timeout=10):
        calls.append((url, timeout))
        return {"harness_healthy": True, "live_state_root": "0xabc", "failed_checks": []}

    monkeypatch.setattr(mod, "_api", fake_api)
    mod._consistency_harness("http://127.0.0.1:18180")
    assert calls
    assert calls[0][1] >= 45.0
    assert "quick=1" in calls[0][0]


def test_p2p_rate_limit_drops_excess_messages():
    from network.p2p_node import P2PNode
    from runtime.config import Config

    cfg = Config()
    cfg.p2p_max_messages_per_sec = 3
    p2p = P2PNode(cfg, None, None)
    assert p2p._rate_limit_ok("peer-a") is True
    assert p2p._rate_limit_ok("peer-a") is True
    assert p2p._rate_limit_ok("peer-a") is True
    assert p2p._rate_limit_ok("peer-a") is False


def test_p2p_strike_bans_after_threshold():
    from network.p2p_node import P2PNode
    from runtime.config import Config

    cfg = Config()
    cfg.p2p_rate_limit_strikes = 2
    cfg.p2p_ban_seconds = 60
    p2p = P2PNode(cfg, None, None)
    peer = PeerConnection(_FakeReader(b""), _FakeWriter())
    peer.peer_id = "bad-peer"
    peer.host = "127.0.0.1"
    peer.port = 9001

    assert p2p._strike_peer_sync(peer, "test") is False
    assert p2p._strike_peer_sync(peer, "test") is True
    assert p2p._is_banned("bad-peer") is True
    sec = p2p.get_p2p_security_status()
    assert sec["active_bans"] == 1
    assert sec["strikes_before_ban"] == 2


@pytest.mark.asyncio
async def test_handle_message_rejects_unknown_wire_type():
    from network.p2p_node import P2PNode
    from runtime.config import Config

    cfg = Config()
    cfg.p2p_rate_limit_strikes = 1
    p2p = P2PNode(cfg, None, None)
    peer = PeerConnection(_FakeReader(b""), _FakeWriter())
    peer.peer_id = "peer-x"
    p2p.peers[peer.peer_id] = peer

    removed = []
    p2p._remove_peer = lambda pid, p: removed.append(pid)

    await p2p._handle_message(peer, {"type": "totally_unknown", "data": {}})
    assert removed == ["peer-x"]
    assert p2p._is_banned("peer-x") is True


def test_p2p_evicts_low_score_peer_when_alternative_exists():
    from network.p2p_node import P2PNode, _peer_health_score
    from runtime.config import Config

    class _Chain:
        def get_height(self):
            return 100

    cfg = Config()
    cfg.p2p_evict_min_score = 50
    p2p = P2PNode(cfg, _Chain(), None)

    good = PeerConnection(_FakeReader(b""), _FakeWriter())
    good.peer_id = "good"
    good.height = 100
    good.last_seen = time.time()

    bad = PeerConnection(_FakeReader(b""), _FakeWriter())
    bad.peer_id = "bad"
    bad.height = 0
    bad.last_seen = time.time() - 999

    p2p.peers = {"good": good, "bad": bad}
    removed = p2p._prune_stale_peers()
    assert removed == 1
    assert "bad" not in p2p.peers
    assert "good" in p2p.peers


def test_peer_health_score_helper():
    from network.p2p_node import _peer_health_score

    assert _peer_health_score(height_gap=0, last_seen_age=0, health_timeout=60) == 100
    assert _peer_health_score(height_gap=3, last_seen_age=0, health_timeout=60) == 55
    assert _peer_health_score(height_gap=0, last_seen_age=70, health_timeout=60) == 50


def test_p2p_maintenance_loop_prunes_stale_peers():
    from network.p2p_node import P2PNode

    class _Chain:
        def get_height(self):
            return 10

    cfg = Config()
    cfg.peer_timeout = 5
    p2p = P2PNode(cfg, _Chain(), None)
    stale = PeerConnection(_FakeReader(b""), _FakeWriter())
    stale.peer_id = "stale"
    stale.last_seen = time.time() - 999
    p2p.peers = {"stale": stale}
    removed = p2p._prune_stale_peers(max_age=30)
    assert removed == 1
    assert "stale" not in p2p.peers


def test_verify_p2p_security_mesh_ok(monkeypatch):
    mod = _load_verify_p2p()
    calls = []

    def fake_api(url, timeout=10):
        calls.append(url)
        if url.endswith("/p2p/security"):
            return {
                "max_message_bytes": 2_097_152,
                "rate_limit_per_sec": 500,
                "strikes_before_ban": 5,
                "active_bans": 0,
            }
        if url.endswith("/status"):
            return {
                "p2p_summary": {
                    "enabled": True,
                    "security": {
                        "max_message_bytes": 2_097_152,
                        "rate_limit_per_sec": 500,
                    },
                }
            }
        raise AssertionError(url)

    monkeypatch.setattr(mod, "_api", fake_api)
    assert mod.verify_p2p_security_mesh(["http://127.0.0.1:8080"]) == 0


def test_verify_p2p_security_mesh_detects_mismatch(monkeypatch):
    mod = _load_verify_p2p()

    def fake_api(url, timeout=10):
        if url.endswith("/p2p/security"):
            return {
                "max_message_bytes": 2_097_152,
                "rate_limit_per_sec": 500,
                "strikes_before_ban": 5,
            }
        if url.endswith("/status"):
            return {
                "p2p_summary": {
                    "enabled": True,
                    "security": {"max_message_bytes": 1024, "rate_limit_per_sec": 500},
                }
            }
        raise AssertionError(url)

    monkeypatch.setattr(mod, "_api", fake_api)
    assert mod.verify_p2p_security_mesh(["http://127.0.0.1:8080"]) == 15

