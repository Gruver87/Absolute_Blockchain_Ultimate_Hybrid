#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Migration: legacy accounts table without code/storage columns."""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from storage.database import Database


def test_accounts_code_storage_columns_migrated(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE accounts (address TEXT PRIMARY KEY, balance REAL, nonce INTEGER)"
    )
    conn.execute(
        "INSERT INTO accounts (address, balance, nonce) VALUES ('0xabc', 10.0, 1)"
    )
    conn.commit()
    conn.close()

    db = Database(db_path)
    rows = db.get_all_accounts()
    assert len(rows) == 1
    assert rows[0]["address"] == "0xabc"
    assert rows[0].get("code") is None or rows[0].get("code") == ""
    assert rows[0].get("storage") is None or rows[0].get("storage") == ""

    cols = {r[1] for r in db.conn.execute("PRAGMA table_info(accounts)").fetchall()}
    assert "code" in cols
    assert "storage" in cols
