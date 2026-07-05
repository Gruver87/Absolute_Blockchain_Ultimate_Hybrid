#!/usr/bin/env python3
"""Mainnet launch checklist smoke test."""

import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "mainnet_launch_checklist",
    ROOT / "scripts" / "mainnet_launch_checklist.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_launch_checklist_passes_non_strict():
    errors, warnings = mod.run_launch_checklist(strict_mainnet=False)
    assert not errors, errors


def test_resolve_launch_manifest_prefers_ceremony_dir(tmp_path):
    ceremony = tmp_path / "ceremony_keys"
    ceremony.mkdir()
    manifest = ceremony / "validators.manifest.json"
    manifest.write_text('{"validators":[]}', encoding="utf-8")
    resolved = mod.resolve_launch_manifest_path(str(ceremony))
    assert resolved == manifest


def test_resolve_launch_manifest_prefers_deployed_when_no_ceremony(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    deployed = data_dir / "validators.manifest.json"
    deployed.write_text('{"validators":[]}', encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    resolved = mod.resolve_launch_manifest_path("", prefer_deployed=True)
    assert resolved == deployed


def test_strict_keys_uses_ceremony_manifest_not_template(tmp_path, monkeypatch):
    """Template example has empty public_key; ceremony manifest must be used for --strict-keys."""
    ceremony = tmp_path / "data" / "ceremony_keys"
    ceremony.mkdir(parents=True)
    manifest = ceremony / "validators.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "validators": [
                    {
                        "index": 1,
                        "node_id": "v1",
                        "address": "0x" + "a" * 40,
                        "mines": True,
                        "public_key": "04" + "b" * 128,
                        "stake": 1000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    template = tmp_path / "validators.manifest.mainnet-v1.example.json"
    template.write_text(
        json.dumps(
            {
                "validators": [
                    {
                        "index": 1,
                        "node_id": "v1",
                        "address": "0x" + "c" * 40,
                        "mines": True,
                        "public_key": "",
                        "stake": 1000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "node.prod.mainnet-v1.example.json"
    config.write_text(
        json.dumps(
            {
                "chain_id": 778888,
                "validators_manifest_path": str(template),
            }
        ),
        encoding="utf-8",
    )

    from runtime.ceremony_keygen import validate_manifest_public_keys
    from runtime.validator_loader import load_manifest

    resolved = mod.resolve_launch_manifest_path(str(ceremony), prefer_deployed=True)
    assert resolved == manifest
    key_errors = validate_manifest_public_keys(
        load_manifest(str(resolved)),
        require_mining_keys=True,
    )
    assert not key_errors, key_errors
