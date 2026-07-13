#!/usr/bin/env python3
"""Production bridge lock receipts and config hardening."""

import os
import tempfile

import pytest

from runtime.config import Config
from storage.database import Database
from bridge.abs_bridge import RustBridge


@pytest.fixture
def prod_bridge(tmp_path, monkeypatch):
    for key in ("ETH_RPC_URL", "BSC_RPC_URL", "POLYGON_RPC_URL", "BRIDGE_ALLOW_SYNTHETIC"):
        monkeypatch.delenv(key, raising=False)
    fd, path = tempfile.mkstemp(suffix=".db", dir=tmp_path)
    os.close(fd)
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.db_path = path
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = __file__
    cfg.bridge_require_l1_proof = True
    db = Database(path)
    db.initialize()
    db.set_balance("0xalice", 100.0)
    br = RustBridge(cfg, db, None)
    yield br, db, cfg
    db.close()
    try:
        os.remove(path)
    except OSError:
        pass


def test_prod_lock_uses_abs_receipt_hash_not_rust_subprocess(prod_bridge, monkeypatch):
    br, db, cfg = prod_bridge

    def _forbidden_rust(*_args, **_kwargs):
        raise AssertionError("prod lock must not call rust without l1_tx_hash")

    monkeypatch.setattr(br, "_call_rust", _forbidden_rust)
    res = br.lock_and_bridge("0xalice", "ethereum", "0xrecipient", 10.0)
    assert res.get("error")
    assert "l1_tx_hash" in res["error"]
    assert db.get_bridge_locks() == []
    assert db.get_balance("0xalice") == 100.0


def test_prod_lock_verifies_l1_via_rust_when_proof_present(prod_bridge, monkeypatch):
    br, db, cfg = prod_bridge
    calls = []

    def _rust_ok(command, args):
        calls.append((command, args))
        return args.get("l1_tx_hash")

    monkeypatch.setattr(br, "_call_rust_ok", lambda command, args: bool(_rust_ok(command, args)))
    monkeypatch.setattr(br, "_call_rust", _rust_ok)
    l1 = "0x" + "ab" * 32
    res = br.lock_and_bridge("0xalice", "ethereum", "0xrecipient", 10.0, l1_tx_hash=l1)
    assert res["tx_hash"] == l1
    assert calls and calls[0][0] == "lock"
    assert calls[0][1]["l1_tx_hash"] == l1


def test_prod_config_forbids_bridge_allow_synthetic(monkeypatch):
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
    monkeypatch.setenv("BRIDGE_ALLOW_SYNTHETIC", "1")
    errs = cfg.validate()
    assert any("BRIDGE_ALLOW_SYNTHETIC" in e for e in errs)
