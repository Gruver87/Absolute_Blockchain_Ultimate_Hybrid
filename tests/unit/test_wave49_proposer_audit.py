"""Wave 49 — block proposer audit log."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def test_proposer_audit_on_block_persist():
    from core.blockchain import Blockchain, Transaction
    from runtime.config import Config
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "p.db"))
    db.initialize()
    cfg = Config()
    miner = "0x" + "a" * 40
    cfg.miner_address = miner
    cfg.burn_address = "0x" + "d" * 40
    db.update_balance(miner, 10_000.0)

    bc = Blockchain(cfg, db)
    tx = Transaction(from_addr=miner, to_addr="0x" + "b" * 40, value=1.0, nonce=0)
    block = bc.create_block([tx], miner)
    assert bc.add_block(block) is True

    log = db.get_proposer_audit_log(limit=5, proposer=miner)
    assert len(log) >= 1
    assert log[0]["height"] == block.height
    assert log[0]["proposer"] == miner
    assert log[0]["tx_count"] == 1


def test_proposer_audit_backfill_from_blocks():
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "b.db")
    db = Database(path)
    db.initialize()
    db.conn.execute(
        """INSERT INTO blocks
           (height, hash, parent_hash, timestamp, miner, tx_count,
            gas_used, total_burned, extra_data, data)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (7, "0xh7", "0xh6", 700, "0xminer1", 2, 0, 0.05, "", "{}"),
    )
    db.conn.commit()

    db2 = Database(path)
    db2.initialize()
    assert db2.count_proposer_audit() >= 1
    detail = db2.get_proposer_detail("0xminer1")
    assert detail["blocks_proposed"] >= 1
    assert detail["last_height"] == 7


def test_proposer_audit_pruned_on_reorg():
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "r.db"))
    db.initialize()
    for h in range(1, 4):
        db._insert_block({
            "height": h,
            "hash": f"hash{h}",
            "parent_hash": f"hash{h-1}" if h > 1 else "0",
            "timestamp": 100 + h,
            "miner": "0xprop",
            "tx_count": 0,
            "total_burned": 0.0,
        })
    db.conn.commit()
    assert db.count_proposer_audit() == 3
    db.truncate_chain_state(1)
    assert db.count_proposer_audit() == 1
