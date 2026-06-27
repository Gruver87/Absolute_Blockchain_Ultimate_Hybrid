"""Wave 48 — address tx index + receipt backfill."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def test_address_tx_index_direction_and_pagination():
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "a.db"))
    db.initialize()
    for i, (fr, to) in enumerate(
        [
            ("0xaaa", "0xbbb"),
            ("0xbbb", "0xccc"),
            ("0xaaa", "0xccc"),
        ],
        start=1,
    ):
        db._persist_block_locked(
            {"height": i, "hash": f"0xblock{i}", "parent_hash": "0",
             "timestamp": 100 + i, "miner": "0xm", "tx_count": 1,
             "gas_used": 0, "total_burned": 0, "extra_data": ""},
            [{
                "hash": f"0xtx{i}", "block_height": i, "from_addr": fr, "to_addr": to,
                "value": float(i), "fee": 0.01, "burned": 0.0, "gas_used": 21000,
                "status": 1, "timestamp": 100 + i,
            }],
        )
    db.conn.commit()

    sent = db.get_transactions_by_address("0xaaa", direction="sent")
    assert len(sent) == 2
    assert all(t["direction"] == "sent" for t in sent)

    recv = db.get_transactions_by_address("0xbbb", direction="received")
    assert len(recv) == 1
    assert recv[0]["direction"] == "received"

    page = db.get_transactions_by_address("0xaaa", limit=1, offset=1)
    assert len(page) == 1

    act = db.get_address_activity("0xaaa")
    assert act["sent_count"] == 2
    assert act["received_count"] == 0
    assert act["tx_count"] == 2
    assert act["last_tx_height"] == 3


def test_receipt_backfill_confirmed_status_string():
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "c.db")
    db = Database(path)
    db.initialize()
    db.conn.execute(
        """INSERT INTO transactions
           (hash, block_height, from_addr, to_addr, value, gas, gas_used,
            fee, burned, nonce, tx_data, status, timestamp)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("0xpool", 2, "0xpoolfrom", "0xpoolto", 1.0, 21000, 21000,
         0.0, 0.0, 0, "", "confirmed", 200),
    )
    db.conn.execute(
        """INSERT INTO blocks
           (height, hash, parent_hash, timestamp, miner, tx_count,
            gas_used, total_burned, extra_data, data)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (2, "0xb2", "0xb1", 200, "0xm", 1, 0, 0.0, "", "{}"),
    )
    db.conn.commit()

    db2 = Database(path)
    db2.initialize()
    assert db2.get_tx_receipt("0xpool") is not None
    assert db2.get_tx_receipt("0xpool")["status"] == 1


def test_receipt_backfill_from_existing_transactions():
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "b.db")
    db = Database(path)
    db.initialize()
    db.conn.execute(
        """INSERT INTO transactions
           (hash, block_height, from_addr, to_addr, value, gas, gas_used,
            fee, burned, nonce, tx_data, status, timestamp)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("0xold", 5, "0xa", "0xb", 3.0, 21000, 21000, 0.1, 0.0, 0, "", 1, 500),
    )
    db.conn.execute(
        """INSERT INTO blocks
           (height, hash, parent_hash, timestamp, miner, tx_count,
            gas_used, total_burned, extra_data, data)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (5, "0xblock5", "0xblock4", 500, "0xm", 1, 0, 0.0, "", "{}"),
    )
    db.conn.commit()

    db2 = Database(path)
    db2.initialize()
    rcpt = db2.get_tx_receipt("0xold")
    assert rcpt is not None
    assert rcpt["block_height"] == 5
    assert rcpt["value"] == 3.0
    m = db2.get_chain_metrics()
    assert m["receipt_count"] >= 1
