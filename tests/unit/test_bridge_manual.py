#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bridge: real DB locks, manual confirm (no auto timer)."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from bridge.abs_bridge import RustBridge


@pytest.fixture
def bridge_env():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.bridge_mode = "simulator"
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


def test_bridge_lock_stays_pending_until_manual_confirm(bridge_env):
    br, db, cfg = bridge_env
    res = br.lock_and_bridge("0xalice", "ethereum", "0xrecipient", 10.0)
    assert "tx_hash" in res
    assert res["status"] == "pending"
    locks = db.get_bridge_locks()
    assert locks[0]["status"] == "pending"

    br._process_pending()
    locks = db.get_bridge_locks()
    assert locks[0]["status"] == "pending"

    ok = br.confirm_lock(res["tx_hash"])
    assert ok["confirmed"] is True
    locks = db.get_bridge_locks()
    assert locks[0]["status"] == "confirmed"


def test_bridge_auto_confirm_when_configured(bridge_env):
    br, db, cfg = bridge_env
    cfg.bridge_auto_confirm_sec = 1
    res = br.lock_and_bridge("0xalice", "bsc", "0xrecipient", 5.0)
    lock = db.get_bridge_locks()[0]
    db.conn.execute(
        "UPDATE bridge_locks SET created_at=? WHERE tx_hash=?",
        (lock["created_at"] - 5, res["tx_hash"]),
    )
    db.conn.commit()
    br._process_pending()
    assert db.get_bridge_locks()[0]["status"] == "confirmed"


def test_bridge_accepts_eth_chain_alias(bridge_env):
    br, db, cfg = bridge_env
    res = br.lock_and_bridge("0xalice", "ETH", "0xrecipient", 10.0)
    assert "tx_hash" in res, res
    assert res["to_chain"] == "ethereum"


def test_rust_bridge_missing_binary_does_not_fallback_to_simulator():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.deployment_mode = "dev"
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = "missing/abs_bridge_bin"
    db = Database(path)
    db.initialize()
    db.set_balance("0xalice", 100.0)
    try:
        br = RustBridge(cfg, db, None)
        assert br._mode == "unavailable"
        res = br.lock_and_bridge("0xalice", "ethereum", "0xrecipient", 10.0)
        assert "bridge unavailable" in res["error"]
        assert db.get_balance("0xalice") == 100.0
    finally:
        db.close()
        try:
            os.remove(path)
        except OSError:
            pass
