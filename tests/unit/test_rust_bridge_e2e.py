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
def rust_bridge_env():
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
