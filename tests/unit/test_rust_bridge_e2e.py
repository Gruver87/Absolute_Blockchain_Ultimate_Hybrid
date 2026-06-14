#!/usr/bin/env python3
"""Bridge lock_and_bridge with BRIDGE_MODE=rust (subprocess CLI)."""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from bridge.abs_bridge import RustBridge

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
BIN = os.path.join(ROOT, "bridge", "abs_bridge_bin")
BIN_EXE = BIN + ".exe"


def _rust_bin():
    if os.path.isfile(BIN_EXE):
        return BIN_EXE
    if os.path.isfile(BIN):
        return BIN
    pytest.skip("bridge/abs_bridge_bin not built — run scripts/build_bridge.ps1")


@pytest.fixture
def rust_bridge_env(monkeypatch):
    """Isolated rust bridge — no L1 RPC from host .env."""
    for key in ("ETH_RPC_URL", "BSC_RPC_URL", "POLYGON_RPC_URL", "BRIDGE_MIN_CONFIRMATIONS"):
        monkeypatch.delenv(key, raising=False)
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    exe = _rust_bin()
    cfg = Config()
    cfg.db_path = path
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = exe
    cfg.bridge_auto_confirm_sec = 0
    cfg.burn_address = "0x" + "d" * 40
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


def test_lock_and_bridge_uses_rust_subprocess(rust_bridge_env):
    br, db, cfg = rust_bridge_env
    assert br._mode == "rust"
    res = br.lock_and_bridge("0xalice", "ethereum", "0xrecipient", 10.0)
    assert "tx_hash" in res
    assert res["tx_hash"].startswith("0x")
    assert len(res["tx_hash"]) == 66
    assert res["status"] == "pending"
    assert db.get_bridge_locks()[0]["status"] == "pending"


def test_confirm_lock_uses_rust_subprocess(rust_bridge_env):
    br, db, cfg = rust_bridge_env
    res = br.lock_and_bridge("0xalice", "bsc", "0xrecipient", 5.0)
    assert res["status"] == "pending"
    ok = br.confirm_lock(res["tx_hash"])
    assert ok["confirmed"] is True
    assert ok.get("mode") == "rust"
    assert db.get_bridge_locks()[0]["status"] == "confirmed"


def test_confirm_incoming_uses_rust_subprocess(rust_bridge_env):
    br, db, cfg = rust_bridge_env
    tx_hash = "0x" + "ab" * 32
    db.save_bridge_lock("0xext", "ethereum", "0xrecipient", 3.0, tx_hash)
    db.set_balance("0xrecipient", 0.0)
    ok = br.confirm_incoming(tx_hash, "0xrecipient", 3.0, "ethereum")
    assert ok["confirmed"] is True, ok
    assert ok.get("mode") == "rust"
    assert db.get_balance("0xrecipient") == 3.0


def test_confirm_incoming_requires_l1_when_rpc_configured(rust_bridge_env, monkeypatch):
    br, db, cfg = rust_bridge_env
    monkeypatch.setenv("ETH_RPC_URL", "https://eth.example")
    tx_hash = "0x" + "cd" * 32
    ok = br.confirm_incoming(tx_hash, "0xrecipient", 1.0, "ethereum")
    assert ok.get("confirmed") is False
    assert "l1_tx_hash" in ok.get("error", "")
