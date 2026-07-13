#!/usr/bin/env python3
"""Public testnet uptime probe tests."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = ROOT / "scripts" / "testnet_uptime_probe.py"
    spec = importlib.util.spec_from_file_location("testnet_uptime_probe", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_uptime_probe_ok():
    mod = _load()
    ready = {"status": "ready"}
    status = {"chain_id": 77777, "height": 12, "peers": 0, "deployment_mode": "dev"}
    harness = {"harness_healthy": True, "tip_state_aligned": True}

    def fake_get(url, timeout=8.0):
        if "/health/ready" in url:
            return ready
        if "/status" in url:
            return status
        return harness

    with patch.object(mod, "_get_json", side_effect=fake_get):
        errors, warnings, meta = mod.run_testnet_uptime_probe()
    assert errors == []
    assert meta.get("ok") is True
    assert any("peer_count=0" in w for w in warnings)


def test_uptime_probe_fails_wrong_chain():
    mod = _load()

    def fake_get(url, timeout=8.0):
        if "/health/ready" in url:
            return {"status": "ready"}
        if "/status" in url:
            return {"chain_id": 1, "height": 1, "peers": 0}
        return {}

    with patch.object(mod, "_get_json", side_effect=fake_get):
        errors, _warnings, meta = mod.run_testnet_uptime_probe(quick_harness=False)
    assert any("chain_id=" in e for e in errors)
    assert meta.get("ok") is False


def test_uptime_write_snapshot(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    path = mod.write_snapshot([], [], {"ok": True})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
