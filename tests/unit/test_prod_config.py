#!/usr/bin/env python3
"""Production/staging config validation rules."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config


def test_staging_config_valid():
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(root, "node.staging.example.json")
    cfg = Config.from_json(path)
    assert cfg.deployment_mode == "staging"
    assert cfg.validate() == []


def test_prod_rejects_simulator_bridge_without_override():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.bridge_mode = "simulator"
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False
    errs = cfg.validate()
    assert any("bridge_mode=rust" in e for e in errs)


def test_prod_requires_jwt_secret():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = __file__  # exists for this test only
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False
    old = os.environ.pop("JWT_SECRET", None)
    try:
        errs = cfg.validate()
        assert any("JWT_SECRET" in e for e in errs)
    finally:
        if old:
            os.environ["JWT_SECRET"] = old
