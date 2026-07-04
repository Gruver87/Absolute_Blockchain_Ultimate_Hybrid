#!/usr/bin/env python3
"""Production/staging config validation rules."""
import os
import json
import sys
import tempfile
import importlib.util
from pathlib import Path

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


def test_prod_requires_native_crypto_flag():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.require_native_crypto = False
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False

    errs = cfg.validate()
    assert any("ABS_REQUIRE_NATIVE_CRYPTO" in e for e in errs)


def test_static_prod_gate_requires_native_crypto(tmp_path, monkeypatch):
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    script_path = os.path.join(root, "scripts", "prod_gate.py")
    spec = importlib.util.spec_from_file_location("prod_gate_for_test", script_path)
    prod_gate = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(prod_gate)

    prod_dir = tmp_path / "docker"
    prod_dir.mkdir()
    config_path = prod_dir / "node.prod.json"
    config = {
        "deployment_mode": "prod",
        "bridge_enabled": False,
        "require_signatures": True,
        "enforce_proposer": True,
        "verify_peer_state_root": True,
        "rpc_api_key_required": True,
        "jwt_enforce_admin": True,
        "require_wallet_file": True,
        "bridge_require_l1_proof": True,
        "cors_origins": ["https://explorer.example.com"],
    }
    for feature in prod_gate.BLOCKED_FEATURES:
        config[feature] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.setattr(prod_gate, "ROOT", Path(tmp_path))
    errors = prod_gate.check_file("docker/node.prod.json")

    assert any("require_native_crypto" in err for err in errors)


def test_prod_rejects_bridge_dev_adapter():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.bridge_dev_adapter_enabled = True
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False
    errs = cfg.validate()
    assert any("BRIDGE_DEV_ADAPTER_ENABLED" in e for e in errs)


def test_prod_requires_jwt_secret():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = __file__  # exists for this test only
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False
    cfg.bridge_oracle_secret = "test-oracle"
    old = os.environ.pop("JWT_SECRET", None)
    try:
        errs = cfg.validate()
        assert any("JWT_SECRET" in e for e in errs)
    finally:
        if old:
            os.environ["JWT_SECRET"] = old


def test_prod_requires_bridge_oracle_secret():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.bridge_enabled = True
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = __file__
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False
    os.environ["JWT_SECRET"] = "x" * 32
    try:
        errs = cfg.validate()
        assert any("BRIDGE_ORACLE_SECRET" in e for e in errs)
    finally:
        os.environ.pop("JWT_SECRET", None)


def test_prod_rejects_placeholder_and_weak_secrets(monkeypatch):
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.bridge_enabled = True
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = __file__
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = True
    cfg.rpc_api_keys = ["your_rpc_key_here"]
    cfg.bridge_oracle_secret = "your_bridge_oracle_hmac_secret"
    monkeypatch.setenv("JWT_SECRET", "your_jwt_secret_here")

    errs = cfg.validate()
    assert any("JWT_SECRET" in e and "placeholder" in e for e in errs)
    assert any("RPC_API_KEYS" in e and "weak" in e for e in errs)
    assert any("BRIDGE_ORACLE_SECRET" in e and "placeholder" in e for e in errs)


def test_prod_bridge_requires_l1_rpc_and_proof_flag(monkeypatch):
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.bridge_enabled = True
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = __file__
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False
    cfg.bridge_oracle_secret = "x" * 32
    cfg.bridge_require_l1_proof = False
    monkeypatch.setenv("JWT_SECRET", "y" * 32)
    monkeypatch.delenv("ETH_RPC_URL", raising=False)
    monkeypatch.delenv("BSC_RPC_URL", raising=False)
    monkeypatch.delenv("POLYGON_RPC_URL", raising=False)

    errs = cfg.validate()
    assert any("L1 RPC URL" in e for e in errs)
    assert any("BRIDGE_REQUIRE_L1_PROOF" in e for e in errs)

    cfg.bridge_require_l1_proof = True
    monkeypatch.setenv("ETH_RPC_URL", "https://rpc.example.com")
    errs = cfg.validate()
    assert not any("L1 RPC URL" in e for e in errs)
    assert not any("BRIDGE_REQUIRE_L1_PROOF" in e for e in errs)


def test_prod_bridge_l1_rpc_probe_when_enabled(monkeypatch):
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.bridge_enabled = True
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = __file__
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False
    cfg.bridge_oracle_secret = "x" * 32
    cfg.bridge_require_l1_proof = True
    monkeypatch.setenv("JWT_SECRET", "y" * 32)
    monkeypatch.setenv("ETH_RPC_URL", "https://rpc.example.com")
    monkeypatch.setenv("BRIDGE_PROBE_L1_RPC", "true")

    monkeypatch.setattr(
        "bridge.l1_rpc.probe_configured_l1_rpcs",
        lambda timeout=5.0: {"ok": False, "error": "ETH_RPC_URL: timeout"},
    )

    errs = cfg.validate()
    assert any("L1 RPC reachability probe failed" in e for e in errs)


def test_non_dev_public_bind_requires_auth_and_cors():
    cfg = Config()
    cfg.deployment_mode = "staging"
    cfg.http_host = "0.0.0.0"
    cfg.rpc_host = "0.0.0.0"
    cfg.jwt_enforce_admin = False
    cfg.rpc_api_key_required = False
    cfg.cors_origins = ["*"]

    errs = cfg.validate()
    assert any("public HTTP bind" in e for e in errs)
    assert any("public RPC bind" in e for e in errs)
    assert any("wildcard CORS" in e for e in errs)


def test_non_dev_public_bind_allowed_when_protected():
    cfg = Config()
    cfg.deployment_mode = "staging"
    cfg.http_host = "0.0.0.0"
    cfg.rpc_host = "0.0.0.0"
    cfg.jwt_enforce_admin = True
    cfg.rpc_api_key_required = True
    cfg.rpc_api_keys = ["x" * 32]
    cfg.cors_origins = ["https://explorer.example.com"]

    errs = cfg.validate()
    assert not any("public HTTP bind" in e for e in errs)
    assert not any("public RPC bind" in e for e in errs)
    assert not any("wildcard CORS" in e for e in errs)


def test_prod_example_json_structure():
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(root, "node.prod.example.json")
    cfg = Config.from_json(path)
    assert cfg.deployment_mode == "prod"
    assert cfg.bridge_mode == "rust"
    assert cfg.jwt_enforce_admin is True
    assert cfg.rpc_api_key_required is True
    assert cfg.bridge_require_l1_proof is True
    assert cfg.require_native_crypto is True
    assert cfg.feature_mev is False
    assert cfg.feature_ai_agents is False


def test_prometheus_alerts_include_rust_bridge_readiness():
    root = Path(__file__).resolve().parents[2]
    alerts = (root / "deploy" / "prometheus" / "alerts.yml").read_text(encoding="utf-8")
    assert "AbsoluteRustBridgeDown" in alerts
    assert "abs_rust_bridge_required == 1 and abs_rust_bridge_ok == 0" in alerts
