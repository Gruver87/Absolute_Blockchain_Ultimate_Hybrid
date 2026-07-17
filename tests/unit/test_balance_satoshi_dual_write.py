#!/usr/bin/env python3
"""Dual-write balance_satoshi on SQLite and helpers."""

import os
import tempfile

from runtime.amount import account_satoshi, dual_write_balance, to_satoshi
from storage.database import Database


def test_sqlite_dual_write_balance_satoshi():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "a.db")
    db = Database(path)
    db.initialize()
    db.set_balance("0x" + "ab" * 20, 12.5)
    assert db.get_balance_satoshi("0x" + "ab" * 20) == to_satoshi(12.5)
    assert abs(db.get_balance("0x" + "ab" * 20) - 12.5) < 1e-12
    db.update_balance("0x" + "ab" * 20, -0.5)
    assert db.get_balance_satoshi("0x" + "ab" * 20) == to_satoshi(12.0)
    row = db.get_account("0x" + "ab" * 20)
    assert row is not None
    assert int(row["balance_satoshi"]) == to_satoshi(12.0)


def test_dual_write_helper_roundtrip():
    row: dict = {"address": "0x1"}
    dual_write_balance(row, "0.000001")
    assert row["balance_satoshi"] == 1
    assert account_satoshi(row) == 1
