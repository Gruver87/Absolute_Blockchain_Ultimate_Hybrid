#!/usr/bin/env python3
"""P2P TLS mesh verify and preflight tests."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_p2p_tls_scripts_exist():
    assert (ROOT / "scripts" / "verify_p2p_tls_mesh.py").is_file()
    assert (ROOT / "scripts" / "p2p_tls_preflight.py").is_file()
    assert (ROOT / "scripts" / "p2p_tls_evidence_suite.ps1").is_file()
    assert (ROOT / "scripts" / "docker_prod_3node_p2ptls.ps1").is_file()


def test_static_tls_material_requires_node_dirs():
    mod = _load("verify_p2p_tls_mesh", "scripts/verify_p2p_tls_mesh.py")
    errors, _warnings, meta = mod.check_static_tls_material()
    assert meta["nodes"]
    assert any("missing TLS file" in e for e in errors)


def test_live_tls_verify_fails_when_not_ready():
    mod = _load("verify_p2p_tls_mesh", "scripts/verify_p2p_tls_mesh.py")
    sec = {"tls": {"enabled": True, "ready": False, "errors": ["cert missing"]}}

    def fake_api(url, timeout=10.0):
        if "/p2p/security" in url:
            return sec
        if "/health/ready" in url:
            return {"status": "ready"}
        return {}

    with patch.object(mod, "_api", side_effect=fake_api), patch.object(mod, "_probe_ready", return_value=True), patch.object(
        mod, "check_static_tls_material", return_value=([], [], {})
    ):
        errors, _warnings, meta = mod.verify_p2p_tls_mesh(check_static=False, require_tls=True)
    assert meta["reachable"] == 3
    assert any("P2P TLS not ready" in e for e in errors)


def test_p2p_tls_preflight_static():
    mod = _load("p2p_tls_preflight", "scripts/p2p_tls_preflight.py")
    errors, _warnings, meta = mod.run_p2p_tls_preflight(live=False)
    assert "deploy_steps" in meta
    assert meta["live"] is False
    assert isinstance(errors, list)
