#!/usr/bin/env python3
"""Prod config validates genesis ceremony manifest."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from runtime.genesis_ceremony import build_from_paths, verify_live_manifest
from runtime.mainnet_constants import MAINNET_V1_CHAIN_ID, ceremony_validator_address


def test_mainnet_v1_manifest_passes_strict_ceremony():
    artifact, errors = build_from_paths(
        "node.prod.mainnet-v1.example.json",
        "validators.manifest.mainnet-v1.example.json",
        strict_addresses=True,
    )
    assert errors == [], errors
    assert artifact["ready"] is True
    assert artifact["mainnet_addresses_ready"] is True
    assert artifact["chain_id"] == MAINNET_V1_CHAIN_ID


def test_ceremony_addresses_match_manifest_seed():
    for index, node_id in (
        (1, "mainnet-v1-validator-1"),
        (2, "mainnet-v1-validator-2"),
        (3, "mainnet-v1-validator-3"),
    ):
        expected = ceremony_validator_address(MAINNET_V1_CHAIN_ID, index, node_id)
        artifact, errors = build_from_paths(
            "node.prod.mainnet-v1.example.json",
            "validators.manifest.mainnet-v1.example.json",
        )
        assert errors == []
        rows = {int(v["index"]): v["address"].lower() for v in artifact["validators"]}
        assert rows[index] == expected.lower()


def test_strict_rejects_repetitive_template_manifest(tmp_path):
    manifest = {
        "version": 1,
        "validators": [
            {
                "index": 1,
                "node_id": "v1",
                "address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",
                "mines": True,
                "stake": 1000,
            }
        ],
    }
    manifest_path = tmp_path / "bad.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(
        json.dumps(
            {
                "network_name": "Test",
                "chain_id": MAINNET_V1_CHAIN_ID,
                "deployment_mode": "prod",
                "validators_manifest_path": str(manifest_path),
            }
        ),
        encoding="utf-8",
    )
    _artifact, errors = build_from_paths(
        str(cfg_path),
        str(manifest_path),
        strict_addresses=True,
    )
    assert any("placeholder_validator_address" in e for e in errors)


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
    cfg.chain_id = MAINNET_V1_CHAIN_ID
    errors = cfg.validate()
    assert not any(e.startswith("validators_manifest:") for e in errors)


def test_genesis_ceremony_hash_pin():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.validators_manifest_path = "validators.manifest.mainnet-v1.example.json"
    cfg.chain_id = MAINNET_V1_CHAIN_ID
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
