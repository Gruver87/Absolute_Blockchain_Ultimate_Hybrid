# tests/unit/test_verify_health_ready_mesh.py
"""Unit tests for Wave A /health/ready mesh gate helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "verify_p2p_ci", ROOT / "scripts" / "verify_p2p_ci.py"
)
assert _SPEC and _SPEC.loader
v = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v)


def test_verify_health_ready_mesh_pass(monkeypatch):
    bodies = {
        "http://n1": {
            "status": "ready",
            "deep_ready": True,
            "checks": {"peers_alive": True},
            "peer_count": 2,
        },
        "http://n2": {
            "status": "ready",
            "deep_ready": True,
            "checks": {"peers_alive": True},
            "peer_count": 2,
        },
    }

    def _fake_api(url, timeout=5):
        base = url.rsplit("/health/ready", 1)[0]
        return bodies[base]

    monkeypatch.setattr(v, "_api", _fake_api)
    monkeypatch.setattr(v.time, "sleep", lambda *_: None)
    assert v.verify_health_ready_mesh(["http://n1", "http://n2"], cycles=3, settle_sec=0) == 0


def test_verify_health_ready_mesh_peers_dead(monkeypatch):
    def _fake_api(url, timeout=5):
        return {
            "status": "not_ready",
            "deep_ready": False,
            "checks": {"peers_alive": False},
            "peer_count": 0,
        }

    monkeypatch.setattr(v, "_api", _fake_api)
    monkeypatch.setattr(v.time, "sleep", lambda *_: None)
    assert v.verify_health_ready_mesh(["http://n1", "http://n2"], cycles=1) == 21
