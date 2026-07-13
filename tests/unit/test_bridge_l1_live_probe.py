#!/usr/bin/env python3
"""Bridge L1 live probe wiring tests."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_bridge_l1_live_probe_module_exists():
    assert (ROOT / "scripts" / "bridge_l1_live_probe.py").is_file()
    assert (ROOT / "scripts" / "bridge_l1_live_probe.ps1").is_file()


def test_run_bridge_l1_live_probe_static_mode():
    mod = _load("bridge_l1_live_probe", "scripts/bridge_l1_live_probe.py")
    with patch("bridge_l1_cutover.run_cutover_gate", return_value=([], ["bridge_disabled"], {"ok": True})):
        errors, warnings, meta = mod.run_bridge_l1_live_probe(probe_l1=False, live=False)
    assert errors == []
    assert meta["mode"] == "static"


def test_write_report_creates_json(tmp_path, monkeypatch):
    mod = _load("bridge_l1_live_probe", "scripts/bridge_l1_live_probe.py")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    path = mod.write_report([], [], {"mode": "probe-l1", "ok": True})
    assert path == tmp_path / "logs" / "bridge_l1_live_probe.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["mode"] == "probe-l1"
    assert payload["ok"] is True


def test_run_gate_accepts_probe_l1_params():
    mr = _load("mainnet_readiness", "scripts/mainnet_readiness.py")
    import inspect

    sig = inspect.signature(mr.run_gate)
    assert "probe_l1" in sig.parameters
    assert "bridge_live" in sig.parameters


def test_cutover_gate_includes_l1_rpc_meta_when_probe_l1(monkeypatch):
    monkeypatch.setenv("ETH_RPC_URL", "https://mainnet.infura.io/v3/testkey")
    cutover = _load("bridge_l1_cutover", "scripts/bridge_l1_cutover.py")
    fake_l1 = {"required": True, "ok": True, "probes": {"ethereum": {"ok": True, "block_number": 123}}}
    with patch("bridge_l1_preflight.run_preflight", return_value=([], [])), patch(
        "bridge.health.check_l1_rpc_health", return_value=fake_l1
    ), patch("runtime.config.Config.from_json") as mock_cfg:
        inst = mock_cfg.return_value
        inst.apply_env = lambda: None
        inst.apply_env_secrets = lambda: None
        _errors, _warnings, meta = cutover.run_cutover_gate(probe_l1=True, live=False)
    assert meta.get("l1_rpc") == fake_l1
