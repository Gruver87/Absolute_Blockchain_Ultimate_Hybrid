#!/usr/bin/env python3
"""Prod smoke profile helpers."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from runtime.prod_smoke_profile import (
    PROD_SMOKE_CHAIN_ID,
    apply_prod_smoke_env,
    prod_node_config,
    write_prod_pair_configs,
)


def test_prod_node_config_has_industrial_flags():
    tmp = tempfile.mkdtemp()
    cfg = prod_node_config(
        tmp,
        node_id="n1",
        http_port=15180,
        p2p_port=15100,
        rpc_port=15145,
        ws_port=15166,
        bootstrap_peers=[],
        bridge_enabled=False,
    )
    assert cfg["deployment_mode"] == "prod"
    assert cfg["chain_id"] == PROD_SMOKE_CHAIN_ID
    assert cfg["evm_require_deploy_salt"] is True
    assert cfg["evm_create2_eip1014"] is True
    assert cfg["bridge_enabled"] is False
    assert cfg["feature_wasm"] is False


def test_prod_smoke_config_validates_with_secrets():
    tmp = tempfile.mkdtemp()
    cfg1, cfg2, _, _ = write_prod_pair_configs(tmp, bridge_enabled=False)
    saved = {k: os.environ.get(k) for k in apply_prod_smoke_env()}
    try:
        for k, v in apply_prod_smoke_env().items():
            os.environ[k] = v
        c1 = Config.from_json(cfg1)
        c1.apply_env()
        errs = c1.validate()
        bridge_missing = [e for e in errs if "rust binary" in e]
        assert not bridge_missing, errs
        assert c1.chain_id == PROD_SMOKE_CHAIN_ID
    finally:
        for k, old in saved.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


def test_write_prod_pair_uses_smoke_manifest_with_wallet_addresses():
    tmp = tempfile.mkdtemp()
    cfg1, cfg2, _, _ = write_prod_pair_configs(tmp, bridge_enabled=False)
    with open(cfg1, encoding="utf-8") as f:
        n1 = json.load(f)
    manifest_path = n1["validators_manifest_path"]
    assert manifest_path.endswith("validators.smoke.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(os.path.join(tmp, "prod-smoke-1", "wallet.json"), encoding="utf-8") as f:
        w1 = json.load(f)
    with open(os.path.join(tmp, "prod-smoke-2", "wallet.json"), encoding="utf-8") as f:
        w2 = json.load(f)
    assert w1["address"] == w2["address"]
    assert manifest["validators"][0]["address"] == w1["address"]
    assert manifest["validators"][0]["mines"] is True
    assert len(manifest["validators"]) == 1


def test_mainnet_v1_example_disables_bridge():
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(root, "node.prod.mainnet-v1.example.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["bridge_enabled"] is False
    assert data["deployment_mode"] == "prod"
    assert data["chain_id"] == PROD_SMOKE_CHAIN_ID
