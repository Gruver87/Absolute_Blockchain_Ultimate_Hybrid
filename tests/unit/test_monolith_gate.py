#!/usr/bin/env python3
"""Monolith gate wiring tests."""

import importlib.util
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def _load(path_rel: str, name: str):
    path = os.path.join(ROOT, path_rel)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_monolith_gate_scripts_exist():
    assert os.path.isfile(os.path.join(ROOT, "scripts", "monolith_gate.py"))
    assert os.path.isfile(os.path.join(ROOT, "scripts", "monolith_gate.ps1"))


def test_industrial_gate_accepts_bridge_cutover_flag():
    mod = _load("scripts/industrial_gate.py", "industrial_gate")
    sig = inspect.signature(mod.run_industrial_gate)
    assert "bridge_cutover" in sig.parameters
    assert "live_prod_mesh" in sig.parameters


def test_launch_checklist_skip_duplicate_gates():
    mod = _load("scripts/mainnet_launch_checklist.py", "mainnet_launch_checklist")
    sig = inspect.signature(mod.run_launch_checklist)
    assert "skip_duplicate_gates" in sig.parameters


def test_monolith_gate_writes_report_path(tmp_path, monkeypatch):
    mod = _load("scripts/monolith_gate.py", "monolith_gate")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    path = mod.write_report([], ["warn"], {"sections": {}})
    assert path.is_file()
    payload = path.read_text(encoding="utf-8")
    assert "monolith_gate.json" in str(path)
    assert "warn" in payload
