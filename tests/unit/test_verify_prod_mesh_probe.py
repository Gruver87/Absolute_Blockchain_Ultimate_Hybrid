#!/usr/bin/env python3
"""Prod mesh probe verification tests."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = ROOT / "scripts" / "verify_prod_mesh_probe.py"
    spec = importlib.util.spec_from_file_location("verify_prod_mesh_probe", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_prod_mesh_probe_scripts_exist():
    assert (ROOT / "scripts" / "verify_prod_mesh_probe.py").is_file()
    assert (ROOT / "scripts" / "probe_prod_mesh.ps1").is_file()
    assert (ROOT / "scripts" / "prod_mesh_resilience_suite.ps1").is_file()


def test_ceremony_evidence_scripts_exist():
    assert (ROOT / "scripts" / "ceremony_evidence_suite.ps1").is_file()
    assert (ROOT / "scripts" / "prepare_ceremony_deploy.ps1").is_file()


def test_unreachable_nodes_fail():
    mod = _load()
    with patch.object(mod, "_probe_ready", return_value=False):
        errors, _warnings, meta = mod.verify_prod_mesh_probe(wait_sec=0)
    assert meta["reachable"] == 0
    assert len(errors) == 3


def test_aligned_mesh_ok_with_mocks():
    mod = _load()
    ready = {"status": "ready"}
    status = {"chain_id": 778888, "height": 10, "peers": 2, "deployment_mode": "prod", "head_hash": "0xabc"}
    harness = {"harness_healthy": True, "tip_state_aligned": True, "live_state_root": "0xroot"}
    topo = {"topology_healthy": True, "peer_count": 2}

    def fake_api(url, timeout=10.0):
        if "/health/ready" in url:
            return ready
        if "/status" in url:
            return status
        if "/p2p/topology" in url:
            return topo
        return harness

    with patch.object(mod, "_api", side_effect=fake_api), patch.object(mod, "_probe_ready", return_value=True):
        errors, _warnings, meta = mod.verify_prod_mesh_probe(wait_sec=0)
    assert errors == []
    assert meta["reachable"] == 3
