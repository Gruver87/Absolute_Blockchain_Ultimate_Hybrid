#!/usr/bin/env python3
"""v1.3.132: resilient bootstrap redial — missing seeds despite sticky peers."""

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


def _node(bootstrap: list[str] | None = None) -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = list(bootstrap or [])
    chain = MagicMock()
    chain.get_height.return_value = 1
    chain.get_state_root.return_value = "aa" * 32
    mempool = MagicMock()
    return P2PNode(cfg, chain, mempool)


def test_needles_v13132():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_missing_bootstrap_addrs" in p2p
    assert "_peer_covers_bootstrap" in p2p
    assert "native_bootstrap_resilient" in p2p
    assert "bootstrap_redial_total" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.132.md").read_text(encoding="utf-8")
    assert "1.3.132-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_bootstrap_resilient" in metrics
    assert "abs_p2p_bootstrap_redial_total" in metrics
    assert "abs_p2p_bootstrap_missing_count" in metrics


def test_missing_bootstrap_when_only_discovery_peer():
    node = _node(["seed.example:5000", "127.0.0.1:5001"])
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "random"
    peer.host = "10.0.0.9"
    peer.port = 9999
    peer.listen_port = 9999
    peer.dial_target = "10.0.0.9:9999"
    node.peers[peer.peer_id] = peer
    missing = node._missing_bootstrap_addrs()
    assert "seed.example:5000" in missing
    assert "127.0.0.1:5001" in missing
    st = node.get_p2p_security_status()
    assert st.get("native_bootstrap_resilient") is True
    assert st.get("bootstrap_missing_count") == 2


def test_bootstrap_covered_by_dial_target_hostname():
    node = _node(["Seed.Example:5000"])
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "seed"
    peer.host = "172.16.1.5"  # resolved IP ≠ hostname
    peer.port = 5000
    peer.listen_port = 5000
    peer.dial_target = "seed.example:5000"
    node.peers[peer.peer_id] = peer
    assert node._missing_bootstrap_addrs() == []


def test_bootstrap_covered_by_host_port_match():
    node = _node(["127.0.0.1:5001"])
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "local"
    peer.host = "127.0.0.1"
    peer.listen_port = 5001
    peer.dial_target = ""
    node.peers[peer.peer_id] = peer
    assert node._missing_bootstrap_addrs() == []


@pytest.mark.asyncio
async def test_bootstrap_retry_dials_missing_despite_peers(monkeypatch):
    node = _node(["seed.example:5000"])
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "sticky"
    peer.host = "10.0.0.1"
    peer.listen_port = 4000
    peer.dial_target = "10.0.0.1:4000"
    node.peers[peer.peer_id] = peer
    node._running = True
    called: list[tuple] = []

    async def _fake_connect(host, port):
        called.append((host, int(port)))
        return False

    node.connect_peer = _fake_connect  # type: ignore[method-assign]
    spawned: list = []
    real_create_task = asyncio.create_task

    def _track_create(coro, *args, **kwargs):
        task = real_create_task(coro, *args, **kwargs)
        spawned.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", _track_create)

    sleeps = 0

    async def _fake_sleep(_sec):
        nonlocal sleeps
        sleeps += 1
        if sleeps >= 2:
            node._running = False

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    await node._bootstrap_retry_loop()
    if spawned:
        await asyncio.gather(*spawned, return_exceptions=True)
    assert ("seed.example", 5000) in called
    assert node._bootstrap_redial_total >= 1


def test_bootstrap_loop_not_sticky_on_any_peer():
    """Regression: any live peer must not cancel bootstrap redials."""
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "if self.peers or not self.config.bootstrap_peers" not in p2p
    assert "_missing_bootstrap_addrs" in p2p
