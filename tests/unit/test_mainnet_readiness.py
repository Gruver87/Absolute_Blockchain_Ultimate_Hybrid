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


def test_mainnet_readiness_strict_audit_blocks_until_complete(monkeypatch):
    gate = _load_mainnet()

    def _pending_audit(*_args, **_kwargs):
        warnings = ["external_audit_pending:Third-party smart-contract / L1 security audit completed"]
        summary = {
            "all_complete": False,
            "total": 8,
            "completed": 7,
            "pending": 1,
            "items": [],
        }
        return warnings, [], summary

    import runtime.external_audit as external_audit

    monkeypatch.setattr(external_audit, "evaluate", _pending_audit)

    errors, warnings, meta = gate.run_gate(live=False, strict_audit=True)
    assert any("external_audit_pending:" in e for e in errors)
    assert meta["sections"]["external_audit"]["all_complete"] is False
    assert "external_checklist" in meta
    assert meta["sections"]["genesis_ceremony"]["ready"] is True


def test_mainnet_readiness_ceremony_hash_pin_env(monkeypatch, tmp_path):
    gate = _load_mainnet()
    from runtime.ceremony_keygen import generate_validator_set
    from runtime.genesis_ceremony import build_from_paths

    template = os.path.join(ROOT, "validators.manifest.mainnet-v1.example.json")
    _manifest, _errors, manifest_path = generate_validator_set(template, str(tmp_path))
    artifact, _ = build_from_paths(
        os.path.join(ROOT, "node.prod.mainnet-v1.example.json"),
        str(manifest_path),
    )
    monkeypatch.setenv("GENESIS_CEREMONY_HASH", artifact["ceremony_hash"])

    errors, warnings, meta = gate.run_gate(
        live=False,
        strict_audit=False,
        ceremony_dir=str(tmp_path),
    )
    assert not any("genesis_ceremony_hash_mismatch" in e for e in errors), errors
    assert meta["sections"]["genesis_ceremony"]["ceremony_hash"] == artifact["ceremony_hash"]


def test_mainnet_readiness_relaxed_audit_passes_automation(monkeypatch):
    monkeypatch.delenv("GENESIS_CEREMONY_HASH", raising=False)
    gate = _load_mainnet()
    errors, warnings, meta = gate.run_gate(live=False, strict_audit=False)
    assert errors == [], errors
    assert len(warnings) >= 1
    path = gate.write_report(errors, warnings, meta)
    assert path.is_file()
