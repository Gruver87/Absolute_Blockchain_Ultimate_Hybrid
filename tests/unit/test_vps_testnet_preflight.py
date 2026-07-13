#!/usr/bin/env python3
"""VPS testnet preflight tests."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_vps_preflight_module_exists():
    assert (ROOT / "scripts" / "vps_testnet_preflight.py").is_file()
    assert (ROOT / "scripts" / "prepare_vps_testnet.ps1").is_file()


def test_vps_preflight_static_ok():
    mod = _load("vps_testnet_preflight", "scripts/vps_testnet_preflight.py")
    errors, warnings, meta = mod.run_vps_testnet_preflight(live=False)
    assert meta.get("chain_id") == 77777
    assert "deploy_steps" in meta
    assert "dns_cutover_probe" in meta
    assert "bootstrap_mesh3_script" in meta
    assert isinstance(warnings, list)


def test_vps_preflight_mesh3_deploy_steps():
    mod = _load("vps_testnet_preflight", "scripts/vps_testnet_preflight.py")
    _errors, _warnings, meta = mod.run_vps_testnet_preflight(live=False, mesh3=True)
    assert any("bootstrap_mesh3" in step for step in meta["deploy_steps"])
    assert any("verify_testnet_mesh.py --mesh3" in step for step in meta["deploy_steps"])


def test_vps_preflight_write_report(tmp_path, monkeypatch):
    mod = _load("vps_testnet_preflight", "scripts/vps_testnet_preflight.py")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    path = mod.write_report([], ["warn"], {"ready": True})
    assert path == tmp_path / "logs" / "vps_testnet_preflight.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
