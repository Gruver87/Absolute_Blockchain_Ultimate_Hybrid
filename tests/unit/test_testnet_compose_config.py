#!/usr/bin/env python3
"""Public testnet Docker configs — static validation."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def _load(name: str) -> dict:
    path = os.path.join(ROOT, "docker", name)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_testnet_seed_config_is_public_devnet():
    cfg = _load("node.testnet.seed.json")
    assert cfg["chain_id"] == 77777
    assert cfg["deployment_mode"] == "dev"
    assert cfg["bridge_enabled"] is False
    assert int(cfg["rate_limit_rpm"]) > 0
    assert cfg["rpc_api_key_required"] is True
    assert cfg["require_native_crypto"] is True
    for key in (
        "feature_zk",
        "feature_wasm",
        "feature_plasma",
        "feature_lightning",
        "feature_pq",
    ):
        assert cfg.get(key) is False


def test_testnet_validator_bootstraps_seed():
    cfg = _load("node.testnet.validator.json")
    assert cfg["chain_id"] == 77777
    assert any("testnet-seed" in p for p in cfg.get("bootstrap_peers", []))
