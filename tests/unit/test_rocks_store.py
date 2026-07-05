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


def test_get_last_block_returns_genesis_at_height_zero(rocks):
    block = {
        "height": 0,
        "hash": "c" * 64,
        "parent_hash": "0" * 64,
        "timestamp": 1700000000,
        "miner": "genesis",
        "state_root": "d" * 64,
        "transactions": [],
    }
    rocks.save_block(block)
    assert rocks.get_chain_tip() == 0
    last = rocks.get_last_block()
    assert last is not None
    assert last["height"] == 0
    assert last["hash"] == "c" * 64


def test_compute_state_root_uses_incremental_accumulator(rocks):
    from runtime.tokenomics import genesis_balances
    from storage import keycodec as kc
    from execution.state_root import compute_state_root_from_blobs

    founder = "0x" + "f" * 40
    for addr, amount in genesis_balances(founder).items():
        rocks.set_balance(addr, float(amount))
    root1 = rocks.compute_state_root()
    rocks.set_balance("0x" + "9" * 40, 1.0)
    root2 = rocks.compute_state_root()
    assert root1 != root2
    blobs = [value for _key, value in rocks._scan_prefix(kc.prefix_accounts())]
    assert root2 == compute_state_root_from_blobs(blobs)


def test_persist_block_atomic_keeps_accumulator_in_sync(rocks):
    from runtime.tokenomics import genesis_balances

    founder = "0x" + "e" * 40
    for addr, amount in genesis_balances(founder).items():
        rocks.set_balance(addr, float(amount))
    before = rocks.compute_state_root()

    block = {
        "height": 1,
        "hash": "f" * 64,
        "parent_hash": "0" * 64,
        "timestamp": 1700000001,
        "miner": founder,
        "state_root": before,
        "tx_count": 0,
        "transactions": [],
    }
    rocks.update_balance("0x" + "1" * 40, 5.0)
    block["state_root"] = rocks.compute_state_root()
    assert rocks.persist_block_atomic(block, [])
    assert rocks.get_live_state_root_meta() == (block["state_root"], 1)
    assert rocks.compute_state_root() == block["state_root"]


def test_state_root_mismatch_audit_on_rocks(rocks):
    rocks.record_state_root_mismatch(
        3,
        expected_root="a" * 64,
        computed_root="b" * 64,
        source="p2p",
        proposer="0x" + "1" * 40,
    )
    rows = rocks.get_state_root_mismatches(limit=5)
    assert len(rows) == 1
    assert rows[0]["height"] == 3
    assert rows[0]["expected_root"] == "a" * 64


def test_reorg_refreshes_live_state_root_meta(rocks):
    from runtime.tokenomics import genesis_balances

    founder = "0x" + "c" * 40
    for addr, amount in genesis_balances(founder).items():
        rocks.set_balance(addr, float(amount))
    roots = []
    for h in range(1, 4):
        root = rocks.compute_state_root()
        roots.append(root)
        rocks.persist_block_atomic(
            {
                "height": h,
                "hash": hex(h)[2:].zfill(64),
                "parent_hash": "0" * 64,
                "timestamp": 1700000000 + h,
                "miner": founder,
                "state_root": root,
                "transactions": [],
            },
            [],
        )
    assert rocks.get_live_state_root_meta() == (roots[-1], 3)
    with rocks.atomic():
        rocks.reorg_truncate_above(1)
    assert rocks.get_chain_tip() == 1
    assert rocks.get_block_by_hash(hex(3)[2:].zfill(64)) is None
    assert rocks.get_live_state_root_meta() == (roots[0], 1)


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


def test_address_tx_index_direction_and_pagination(rocks):
    for i, (fr, to) in enumerate(
        [
            ("0xaaa", "0xbbb"),
            ("0xbbb", "0xccc"),
            ("0xaaa", "0xccc"),
        ],
        start=1,
    ):
        rocks.persist_block_atomic(
            {
                "height": i,
                "hash": hex(i)[2:].zfill(64),
                "parent_hash": "0" * 64,
                "timestamp": 100 + i,
                "miner": "0x" + "1" * 40,
                "tx_count": 1,
                "transactions": [],
            },
            [
                {
                    "hash": hex(i + 100)[2:].zfill(64),
                    "block_height": i,
                    "from_addr": fr,
                    "to_addr": to,
                    "value": float(i),
                    "fee": 0.01,
                    "burned": 0.0,
                    "gas_used": 21000,
                    "status": 1,
                    "timestamp": 100 + i,
                }
            ],
        )

    sent = rocks.get_transactions_by_address("0xaaa", direction="sent")
    assert len(sent) == 2
    assert all(t["direction"] == "sent" for t in sent)

    recv = rocks.get_transactions_by_address("0xbbb", direction="received")
    assert len(recv) == 1
    assert recv[0]["direction"] == "received"

    page = rocks.get_transactions_by_address("0xaaa", limit=1, offset=1)
    assert len(page) == 1

    act = rocks.get_address_activity("0xaaa")
    assert act["sent_count"] == 2
    assert act["received_count"] == 0
    assert act["tx_count"] == 2
    assert act["last_tx_height"] == 3


def test_reorg_removes_address_tx_indexes(rocks):
    rocks.persist_block_atomic(
        {
            "height": 1,
            "hash": "a" * 64,
            "parent_hash": "0" * 64,
            "timestamp": 1700000001,
            "miner": "0x" + "1" * 40,
            "transactions": [],
        },
        [
            {
                "hash": "b" * 64,
                "block_height": 1,
                "from_addr": "0x" + "2" * 40,
                "to_addr": "0x" + "3" * 40,
                "value": 1.0,
                "gas": 21000,
                "fee": 0.1,
                "burned": 0.0,
                "nonce": 0,
                "status": 1,
                "timestamp": 1700000002,
            }
        ],
    )
    sender = "0x" + "2" * 40
    assert rocks.count_transactions_by_address(sender, "sent") == 1
    with rocks.atomic():
        rocks.reorg_truncate_above(0)
    assert rocks.count_transactions_by_address(sender, "sent") == 0


def test_get_recent_transactions_uses_index(rocks):
    for i in range(1, 4):
        rocks.persist_block_atomic(
            {
                "height": i,
                "hash": f"{i:064x}",
                "parent_hash": f"{i - 1:064x}" if i > 1 else "0" * 64,
                "timestamp": 1700000000 + i,
                "miner": "0x" + "1" * 40,
                "transactions": [],
            },
            [
                {
                    "hash": f"0x{(i + 100):064x}",
                    "block_height": i,
                    "from_addr": "0x" + "a" * 40,
                    "to_addr": "0x" + "b" * 40,
                    "value": 1.0,
                    "gas": 21000,
                    "fee": 0.1,
                    "burned": 0.0,
                    "nonce": i - 1,
                    "status": 1,
                    "timestamp": 1700000100 + i,
                }
            ],
        )
    recent = rocks.get_recent_transactions(limit=2)
    assert len(recent) == 2
    assert recent[0]["block_height"] == 3
    assert recent[1]["block_height"] == 2


def test_reorg_removes_recent_tx_index(rocks):
    rocks.persist_block_atomic(
        {
            "height": 1,
            "hash": "a" * 64,
            "parent_hash": "0" * 64,
            "timestamp": 1700000001,
            "miner": "0x" + "1" * 40,
            "transactions": [],
        },
        [
            {
                "hash": "b" * 64,
                "block_height": 1,
                "from_addr": "0x" + "2" * 40,
                "to_addr": "0x" + "3" * 40,
                "value": 1.0,
                "gas": 21000,
                "fee": 0.1,
                "burned": 0.0,
                "nonce": 0,
                "status": 1,
                "timestamp": 1700000002,
            }
        ],
    )
    assert len(rocks.get_recent_transactions(limit=10)) == 1
    with rocks.atomic():
        rocks.reorg_truncate_above(0)
    assert rocks.get_recent_transactions(limit=10) == []


def test_bridge_lock_and_credit(rocks):
    rocks.save_bridge_lock("0xalice", "ethereum", "0xrecipient", 10.0, "0x" + "11" * 32)
    locks = rocks.get_bridge_locks()
    assert len(locks) == 1
    assert locks[0]["status"] == "pending"
    assert locks[0]["tx_hash"] == "0x" + "11" * 32
    rocks.confirm_bridge_lock("0x" + "11" * 32)
    assert rocks.get_bridge_locks()[0]["status"] == "confirmed"
    l1 = "0x" + "aa" * 32
    key = rocks.save_bridge_credit(l1, "0xrecipient", 10.0, "ethereum")
    assert rocks.has_bridge_credit(key)
    assert rocks.bridge_credit_key(l1, "0xrecipient", 10.0, "ethereum") == key
    assert rocks.save_bridge_credit(l1, "0xrecipient", 10.0, "ethereum") == key


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
