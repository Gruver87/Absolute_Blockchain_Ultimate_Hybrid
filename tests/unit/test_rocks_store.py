#!/usr/bin/env python3
"""RocksDB chain store tests (skipped when native RocksEngine is unavailable)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import abs_native  # type: ignore

    HAS_ROCKS = hasattr(abs_native, "RocksEngine")
except Exception:
    HAS_ROCKS = False

pytestmark = pytest.mark.skipif(not HAS_ROCKS, reason="abs_native.RocksEngine not built")


@pytest.fixture
def rocks(tmp_path):
    from storage.rocks_store import RocksChainStore

    path = str(tmp_path / "chainstore")
    store = RocksChainStore(path, synchronous="FULL")
    store.initialize()
    yield store
    store.close()


def test_persist_block_atomic(rocks):
    from runtime.tokenomics import genesis_balances

    for addr, amount in genesis_balances("0x" + "1" * 40).items():
        rocks.set_balance(addr, float(amount))
    assert rocks.get_balance("0xecosystem000000000000000000000000000001") > 0
    assert rocks.get_balance("0xtreasury00000000000000000000000000001") > 0

    block = {
        "height": 1,
        "hash": "a" * 64,
        "parent_hash": "0" * 64,
        "timestamp": 1700000000,
        "miner": "0x" + "1" * 40,
        "tx_count": 1,
        "transactions": [],
    }
    txs = [
        {
            "hash": "b" * 64,
            "block_height": 1,
            "from_addr": "0x" + "2" * 40,
            "to_addr": "0x" + "3" * 40,
            "value": 1.0,
            "gas": 21000,
            "fee": 0.1,
            "burned": 0.5,
            "nonce": 0,
            "status": 1,
            "timestamp": 1700000001,
        }
    ]
    burn_addr = "0x" + "d" * 40
    assert rocks.persist_block_atomic(block, txs, burned_amount=0.5, burn_address=burn_addr)
    assert rocks.get_chain_tip() == 1
    assert rocks.get_block(1) is not None
    assert len(rocks.get_transactions_in_block(1)) == 1
    assert rocks.get_total_burned() == pytest.approx(0.5)
    assert rocks.get_balance(burn_addr) == pytest.approx(0.5)
    receipts = rocks.get_receipts_by_block(1)
    assert len(receipts) == 1
    audit = rocks.get_proposer_audit_log(limit=5, proposer="0x" + "1" * 40)
    assert len(audit) == 1
    by_addr = rocks.get_transactions_by_address("0x" + "2" * 40, direction="sent")
    assert len(by_addr) == 1


def test_reorg_truncate_and_reset(rocks):
    for h in range(1, 4):
        rocks.persist_block_atomic(
            {
                "height": h,
                "hash": hex(h)[2:].zfill(64),
                "parent_hash": "0" * 64,
                "timestamp": 1700000000 + h,
                "miner": "0x" + "1" * 40,
                "transactions": [],
            },
            [],
        )
    assert rocks.get_chain_tip() == 3
    with rocks.atomic():
        rocks.reorg_truncate_above(1)
        rocks.reset_accounts_from_alloc({"0x" + "a" * 40: 100.0}, _in_atomic=True)
    assert rocks.get_chain_tip() == 1
    assert rocks.get_block(2) is None
    assert rocks.get_balance("0x" + "a" * 40) == pytest.approx(100.0)


def test_hybrid_factory(tmp_path):
    from runtime.config import Config
    from storage.factory import open_database

    cfg = Config()
    cfg.db_engine = "rocksdb"
    cfg.db_path = str(tmp_path / "chainstore")
    cfg.sqlite_synchronous = "NORMAL"
    cfg.rocksdb_sync = "FULL"
    db = open_database(cfg)
    db.initialize()
    assert getattr(db, "engine", "") == "rocksdb_hybrid"
    db.save_block({"height": 0, "hash": "0" * 64, "miner": "genesis", "transactions": []})
    assert db.get_chain_tip() == 0
    db.close()


def test_sqlite_to_rocks_migration(tmp_path):
    from storage.database import Database

    src_path = str(tmp_path / "legacy.db")
    dest_path = str(tmp_path / "chainstore")
    db = Database(src_path)
    db.initialize()
    block = {
        "height": 1,
        "hash": "c" * 64,
        "parent_hash": "0" * 64,
        "timestamp": 1700000000,
        "miner": "0x" + "4" * 40,
        "transactions": [],
    }
    txs = [
        {
            "hash": "d" * 64,
            "block_height": 1,
            "from_addr": "0x" + "5" * 40,
            "to_addr": "0x" + "6" * 40,
            "value": 2.0,
            "gas": 21000,
            "fee": 0.2,
            "burned": 0.1,
            "nonce": 0,
            "status": 1,
            "timestamp": 1700000002,
        }
    ]
    db.persist_block_atomic(block, txs, burned_amount=0.1, burn_address="0x" + "e" * 40)
    db.close()

    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/migrate_sqlite_to_rocks.py",
            "--source",
            src_path,
            "--dest",
            dest_path,
            "--verify",
        ],
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
