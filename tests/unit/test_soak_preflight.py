#!/usr/bin/env python3
"""Soak preflight wiring tests."""

import importlib.util
import os
import sys
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def _load(name: str, rel: str):
    path = os.path.join(ROOT, rel)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_soak_preflight_module_exists():
    assert os.path.isfile(os.path.join(ROOT, "scripts", "soak_preflight.py"))
    assert os.path.isfile(os.path.join(ROOT, "scripts", "prepare_48h_soak.ps1"))


def test_soak_preflight_detects_unreachable_mesh(monkeypatch):
    mod = _load("soak_preflight", "scripts/soak_preflight.py")

    def _fail_urlopen(*_args, **_kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _fail_urlopen)
    errors, _warnings, meta = mod.run_soak_preflight(hours=48)
    assert errors
    assert meta.get("ready") is False
    assert "start_command" in meta
    assert meta.get("hours_planned") == 48


def test_monolith_gate_accepts_soak_preflight_flag():
    mod = _load("monolith_gate", "scripts/monolith_gate.py")
    import inspect

    sig = inspect.signature(mod.run_monolith_gate)
    assert "soak_preflight" in sig.parameters


def test_soak_preflight_write_report(tmp_path, monkeypatch):
    mod = _load("soak_preflight", "scripts/soak_preflight.py")
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    path = mod.write_report([], ["warn"], {"ready": True})
    assert path == tmp_path / "logs" / "soak_preflight.json"
    assert path.is_file()
    payload = path.read_text(encoding="utf-8")
    assert "warn" in payload
