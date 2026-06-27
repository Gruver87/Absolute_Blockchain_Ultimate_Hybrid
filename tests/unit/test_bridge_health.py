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
