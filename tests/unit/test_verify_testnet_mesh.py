#!/usr/bin/env python3
"""Public testnet mesh verification tests."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = ROOT / "scripts" / "verify_testnet_mesh.py"
    spec = importlib.util.spec_from_file_location("verify_testnet_mesh", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_verify_testnet_mesh_module_exists():
    assert (ROOT / "scripts" / "verify_testnet_mesh.py").is_file()
    assert (ROOT / "scripts" / "docker_testnet_mesh.ps1").is_file()
    assert (ROOT / "scripts" / "docker_testnet_mesh3.ps1").is_file()
    assert (ROOT / "scripts" / "testnet_health_watch.ps1").is_file()


def test_solo_seed_warns_without_validator():
    mod = _load()
    ready = {"status": "ready"}
    status = {"chain_id": 77777, "height": 3, "peers": 0}
    harness = {"harness_healthy": True, "tip_state_aligned": True}
    mesh = {"peer_count": 0, "expected_peers": 1, "mesh_healthy": False, "height_aligned": True}

    def fake_api(url, timeout=10.0):
        if "/health/ready" in url:
            return ready
        if "/status" in url:
            return status
        if "/testnet/mesh" in url:
            return mesh
        return harness

    with patch.object(mod, "_api", side_effect=fake_api), patch.object(mod, "_probe_health", return_value=True):
        errors, warnings, meta = mod.verify_testnet_mesh(wait_sec=0)
    assert errors == []
    assert any("solo seed" in w for w in warnings)
    assert meta["reachable"] == 1


def test_two_node_mesh_fails_when_not_healthy():
    mod = _load()
    ready = {"status": "ready"}
    status = {"chain_id": 77777, "height": 5, "peers": 1}
    harness = {"harness_healthy": True, "tip_state_aligned": True}
    mesh = {"peer_count": 0, "expected_peers": 1, "mesh_healthy": False, "height_aligned": True}

    def fake_api(url, timeout=10.0):
        if "/health/ready" in url:
            return ready
        if "/status" in url:
            return status
        if "/testnet/mesh" in url:
            return mesh
        return harness

    with patch.object(mod, "_api", side_effect=fake_api), patch.object(mod, "_probe_health", return_value=True):
        errors, _warnings, meta = mod.verify_testnet_mesh(
            validator_urls=["http://127.0.0.1:19081"],
            wait_sec=0,
        )
    assert meta["reachable"] == 2
    assert any("mesh_healthy=false" in e for e in errors)


def test_mesh3_expects_three_nodes():
    mod = _load()
    with patch.object(mod, "_probe_health", return_value=False):
        errors, _warnings, meta = mod.verify_testnet_mesh(
            validator_urls=list(mod.DEFAULT_MESH3),
            wait_sec=0,
        )
    assert meta["expected"] == 3
    assert len(errors) >= 3
