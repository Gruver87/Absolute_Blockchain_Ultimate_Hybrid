#!/usr/bin/env python3
"""Mainnet readiness gate smoke tests."""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def _load_mainnet():
    path = os.path.join(ROOT, "scripts", "mainnet_readiness.py")
    spec = importlib.util.spec_from_file_location("mainnet_readiness", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_mainnet_readiness_passes():
    gate = _load_mainnet()
    errors, warnings, meta = gate.run_gate(live=False)
    assert errors == [], errors
    assert "external_checklist" in meta
    assert meta["sections"]["genesis_ceremony"]["ready"] is True
    assert "external_audit" in meta["sections"]
    assert meta["sections"]["external_audit"]["all_complete"] is False
    assert len(warnings) >= 1
    path = gate.write_report(errors, warnings, meta)
    assert path.is_file()
