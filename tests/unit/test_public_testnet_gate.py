#!/usr/bin/env python3
"""Public testnet gate tests."""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def _load_gate():
    path = os.path.join(ROOT, "scripts", "public_testnet_gate.py")
    spec = importlib.util.spec_from_file_location("public_testnet_gate", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_public_testnet_gate_static_ok():
    mod = _load_gate()
    errors, warnings, meta = mod.run_public_testnet_gate(live=False)
    assert errors == [], errors
    assert meta.get("chain_id") == 77777
    assert any("public_dns_tls" in w for w in warnings)


def test_public_testnet_gate_requires_soak_when_configured(tmp_path):
    mod = _load_gate()
    soak = tmp_path / "soak.json"
    soak.write_text(
        '{"hours_requested": 7, "passed": true}',
        encoding="utf-8",
    )
    errors, _warnings, _meta = mod.run_public_testnet_gate(
        require_soak_hours=48,
        soak_report=str(soak),
    )
    assert any("hours_requested=7" in e for e in errors)
