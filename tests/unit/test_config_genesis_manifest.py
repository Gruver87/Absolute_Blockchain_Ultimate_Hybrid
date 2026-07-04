#!/usr/bin/env python3
"""Prod config validates genesis ceremony manifest."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from runtime.genesis_ceremony import build_from_paths, verify_live_manifest


def test_mainnet_v1_manifest_passes_strict_ceremony():
    artifact, errors = build_from_paths(
        "node.prod.mainnet-v1.example.json",
        "validators.manifest.mainnet-v1.example.json",
        strict_addresses=True,
    )
    assert errors == [], errors
    assert artifact["ready"] is True
    assert artifact["mainnet_addresses_ready"] is True


def test_verify_live_manifest_rejects_placeholder_when_strict():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.validators_manifest_path = "validators.manifest.example.json"
    errors, artifact = verify_live_manifest(cfg, strict_addresses=True)
    assert any("placeholder_validator_address" in e for e in errors)
    assert artifact.get("mainnet_addresses_ready") is False


def test_prod_config_validate_requires_manifest_path():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False
    cfg.validators_manifest_path = ""
    errors = cfg.validate()
    assert any("validators_manifest_path" in e for e in errors)


def test_prod_config_validate_accepts_mainnet_v1_manifest():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False
    cfg.bridge_enabled = False
    cfg.validators_manifest_path = "validators.manifest.mainnet-v1.example.json"
    cfg.chain_id = 778888
    errors = cfg.validate()
    assert not any(e.startswith("validators_manifest:") for e in errors)


def test_genesis_ceremony_hash_pin():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.validators_manifest_path = "validators.manifest.mainnet-v1.example.json"
    cfg.chain_id = 778888
    _errors, artifact = verify_live_manifest(cfg)
    pinned = artifact["ceremony_hash"]
    errors, _ = verify_live_manifest(
        cfg,
        expected_ceremony_hash=pinned,
    )
    assert errors == []
    errors, _ = verify_live_manifest(
        cfg,
        expected_ceremony_hash="0" * 64,
    )
    assert any("genesis_ceremony_hash_mismatch" in e for e in errors)
