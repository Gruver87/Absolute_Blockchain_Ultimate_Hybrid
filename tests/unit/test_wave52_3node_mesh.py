"""Wave 52 — 3-node testnet mesh API."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
from wave_expect import EXPECTED_API_WAVE


class _FakeP2P:
    def __init__(self, peers, consistent=True):
        self._peers = peers
        self._state_consistent = consistent

    def get_peers_info(self):
        return self._peers


class _FakeBC:
    def __init__(self, height=100, root="0xabc"):
        self._height = height
        self._root = root

    def get_height(self):
        return self._height

    def get_state_root(self):
        return self._root


class _FakeCfg:
    node_id = "docker-node-1"
    chain_id = 77777
    testnet_expected_peers = 2
    bootstrap_peers = []


def test_mesh_healthy_hub_node():
    from api.http import _build_testnet_mesh

    p2p = _FakeP2P([
        {"id": "docker-node-2", "host": "node2", "port": 5000, "height": 100, "head": "0x1", "connected_for": 30},
        {"id": "docker-node-3", "host": "node3", "port": 5000, "height": 99, "head": "0x2", "connected_for": 25},
    ])
    mesh = _build_testnet_mesh(p2p, _FakeBC(), _FakeCfg())
    assert mesh["peer_count"] == 2
    assert mesh["mesh_healthy"] is True
    assert mesh["testnet_mode"] == "3-node"
    assert mesh["api_wave"] == EXPECTED_API_WAVE


def test_mesh_unhealthy_low_peers():
    from api.http import _build_testnet_mesh

    p2p = _FakeP2P([
        {"id": "docker-node-2", "host": "node2", "port": 5000, "height": 100, "head": "0x1", "connected_for": 10},
    ])
    mesh = _build_testnet_mesh(p2p, _FakeBC(), _FakeCfg())
    assert mesh["mesh_healthy"] is False
    assert mesh["expected_peers"] == 2


def test_mesh_height_gap_breaks_health():
    from api.http import _build_testnet_mesh

    p2p = _FakeP2P([
        {"id": "docker-node-2", "host": "node2", "port": 5000, "height": 50, "head": "0x1", "connected_for": 10},
        {"id": "docker-node-3", "host": "node3", "port": 5000, "height": 100, "head": "0x2", "connected_for": 10},
    ])
    mesh = _build_testnet_mesh(p2p, _FakeBC(height=100), _FakeCfg())
    assert mesh["max_peer_height_gap"] == 50
    assert mesh["mesh_healthy"] is False
