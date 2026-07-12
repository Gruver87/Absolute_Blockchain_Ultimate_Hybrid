#!/usr/bin/env python3
"""Ceremony preflight gate tests."""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def _load_preflight():
    path = os.path.join(ROOT, "scripts", "ceremony_preflight.py")
    spec = importlib.util.spec_from_file_location("ceremony_preflight", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_ceremony_preflight_ok_with_generated_dir(tmp_path, monkeypatch):
    mod = _load_preflight()
    from runtime.ceremony_keygen import generate_validator_set
    from runtime.genesis_ceremony import build_from_paths

    template = os.path.join(ROOT, "validators.manifest.mainnet-v1.example.json")
    _manifest, _errors, manifest_path = generate_validator_set(template, str(tmp_path))
    artifact, _ = build_from_paths(
        os.path.join(ROOT, "node.prod.mainnet-v1.example.json"),
        str(manifest_path),
    )
    monkeypatch.setenv("GENESIS_CEREMONY_HASH", artifact["ceremony_hash"])

    errors, warnings, meta = mod.run_ceremony_preflight(
        str(tmp_path),
        require_env_pin=True,
    )
    assert errors == [], errors
    assert meta["ceremony_hash"] == artifact["ceremony_hash"]


def test_ceremony_preflight_hash_mismatch(tmp_path, monkeypatch):
    mod = _load_preflight()
    from runtime.ceremony_keygen import generate_validator_set

    template = os.path.join(ROOT, "validators.manifest.mainnet-v1.example.json")
    generate_validator_set(template, str(tmp_path))
    monkeypatch.setenv("GENESIS_CEREMONY_HASH", "0" * 64)

    errors, _warnings, _meta = mod.run_ceremony_preflight(
        str(tmp_path),
        require_env_pin=True,
    )
    assert any("GENESIS_CEREMONY_HASH mismatch" in e for e in errors)
