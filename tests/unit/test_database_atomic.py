#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты атомарного сохранения блоков."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from storage.database import Database


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "atomic.db")
    database = Database(path)
    database.initialize()
    yield database
    database.close()


def test_persist_block_atomic_all_or_nothing(db):
    block = {
        "height": 1,
        "hash": "abc123",
        "parent_hash": "0" * 64,
        "timestamp": 1700000000,
        "miner": "0xminer",
        "tx_count": 1,
        "gas_used": 21000,
        "total_burned": 0.5,
        "extra_data": "",
        "transactions": [],
    }
    txs = [{
        "hash": "tx1",
        "block_height": 1,
        "from_addr": "0xfrom",
        "to_addr": "0xto",
        "value": 1.0,
        "gas": 21000,
        "fee": 0.1,
        "burned": 0.5,
        "nonce": 0,
        "status": 1,
        "timestamp": 1700000001,
    }]
    burn_addr = "0xdead"

    assert db.persist_block_atomic(block, txs, burned_amount=0.5, burn_address=burn_addr)
    assert db.get_block(1) is not None
    assert len(db.get_transactions_in_block(1)) == 1
    assert db.get_total_burned() == pytest.approx(0.5)
    assert db.get_balance(burn_addr) == pytest.approx(0.5)


def test_backup_to_creates_file(db, tmp_path):
    dest = str(tmp_path / "backups" / "copy.db")
    assert db.backup_to(dest)
    assert os.path.isfile(dest)
    restored = Database(dest)
    assert restored.get_chain_tip() == db.get_chain_tip()
    restored.close()
