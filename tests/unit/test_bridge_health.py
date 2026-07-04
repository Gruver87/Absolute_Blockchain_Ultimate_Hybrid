#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rust bridge runtime health checks."""

from types import SimpleNamespace

from bridge import health
from runtime.config import Config


def test_rust_bridge_health_accepts_ready_json(monkeypatch, tmp_path):
    binary = tmp_path / "abs_bridge_bin"
    binary.write_text("placeholder", encoding="utf-8")

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout='{"status":"ready","source":"abs_bridge_bin_v4"}',
            stderr="",
        )

    monkeypatch.setattr(health.subprocess, "run", fake_run)

    out = health.check_rust_bridge_binary(str(binary))
    assert out["ok"] is True
    assert out["response"]["status"] == "ready"


def test_rust_bridge_health_rejects_invalid_json(monkeypatch, tmp_path):
    binary = tmp_path / "abs_bridge_bin"
    binary.write_text("placeholder", encoding="utf-8")

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout="not-json", stderr="")

    monkeypatch.setattr(health.subprocess, "run", fake_run)

    out = health.check_rust_bridge_binary(str(binary))
    assert out["ok"] is False
    assert "invalid JSON" in out["error"]


def test_l1_rpc_health_without_urls():
    out = health.check_l1_rpc_health()
    assert out["configured"] is False
    assert out["ok"] is True


def test_l1_rpc_health_probes_when_enabled(monkeypatch):
    monkeypatch.setenv("ETH_RPC_URL", "http://eth")
    monkeypatch.setenv("BRIDGE_PROBE_L1_RPC", "true")
    monkeypatch.setattr(
        "bridge.l1_rpc.probe_configured_l1_rpcs",
        lambda timeout=5.0: {"ok": True, "probes": {"ETH_RPC_URL": {"ok": True}}},
    )
    out = health.check_l1_rpc_health(timeout=1.0)
    assert out["configured"] is True
    assert out["ok"] is True
    assert "ETH_RPC_URL" in out["endpoints"]


def test_l1_rpc_health_required_in_prod(monkeypatch):
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.bridge_enabled = True
    cfg.bridge_require_l1_proof = True
    monkeypatch.delenv("ETH_RPC_URL", raising=False)
    out = health.check_l1_rpc_health(cfg)
    assert out["required"] is True
    assert out["ok"] is False


def test_prod_config_requires_rust_bridge_smoke(monkeypatch, tmp_path):
    binary = tmp_path / "abs_bridge_bin"
    binary.write_text("placeholder", encoding="utf-8")

    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.bridge_enabled = True
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = str(binary)
    cfg.require_wallet_file = False
    cfg.rpc_api_key_required = False
    cfg.bridge_oracle_secret = "x" * 32
    cfg.bridge_require_l1_proof = True

    monkeypatch.setenv("JWT_SECRET", "y" * 32)
    monkeypatch.setenv("ETH_RPC_URL", "https://rpc.example.com")
    monkeypatch.setattr(
        health,
        "check_rust_bridge_binary",
        lambda path: {"ok": False, "error": "bad bridge json", "path": path},
    )

    errs = cfg.validate()
    assert any("rust binary smoke-test failed" in e for e in errs)
    assert any("bad bridge json" in e for e in errs)
