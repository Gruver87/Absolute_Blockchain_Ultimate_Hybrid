#!/usr/bin/env python3
"""Genesis ceremony artifact builder tests."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.genesis_ceremony import (
    build_ceremony_artifact,
    genesis_alloc_hash,
    validate_manifest_for_mainnet,
    validator_set_hash,
)
from runtime.validator_loader import load_manifest


def test_validator_set_hash_stable():
    manifest = load_manifest("validators.manifest.example.json")
    h1 = validator_set_hash(manifest)
    h2 = validator_set_hash(manifest)
    assert h1 == h2
    assert len(h1) == 64


def test_build_ceremony_artifact_ready():
    manifest = load_manifest("validators.manifest.example.json")
    cfg = {
        "network_name": "Absolute",
        "chain_id": 77777,
        "deployment_mode": "prod",
    }
    artifact = build_ceremony_artifact(
        cfg,
        manifest,
        "validators.manifest.example.json",
    )
    assert artifact["ready"] is True
    assert artifact["validators_count"] >= 3
    assert artifact["ceremony_hash"]
    assert artifact["genesis_alloc_hash"] == genesis_alloc_hash("")
    assert validate_manifest_for_mainnet(manifest) == []


def test_manifest_without_addresses_fails():
    bad = {"validators": [{"node_id": "x", "stake": 100}]}
    errors = validate_manifest_for_mainnet(bad)
    assert "manifest_must_list_explicit_0x_addresses" in errors


def test_strict_mainnet_rejects_placeholder_addresses():
    manifest = load_manifest("validators.manifest.example.json")
    errors = validate_manifest_for_mainnet(manifest, strict_addresses=True)
    assert any(e.startswith("placeholder_validator_address:") for e in errors)
