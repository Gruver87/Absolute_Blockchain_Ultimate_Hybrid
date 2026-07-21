#!/usr/bin/env python3
"""SQLite reorg parity with Rocks (evm_logs + tx_propagation)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from storage.database import Database


def test_sqlite_reorg_purges_evm_logs_and_tx_prop():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    Path(path).unlink(missing_ok=True)
    db = Database(path)
    db.initialize()
    try:
        assert db.save_block(
            {
                "number": 1,
                "height": 1,
                "hash": "aa" * 32,
                "previous_hash": "00" * 32,
                "parent_hash": "00" * 32,
                "timestamp": 1,
                "transactions": [],
                "state_root": "11" * 32,
            }
        )
        assert db.save_block(
            {
                "number": 2,
                "height": 2,
                "hash": "bb" * 32,
                "previous_hash": "aa" * 32,
                "parent_hash": "aa" * 32,
                "timestamp": 2,
                "transactions": [],
                "state_root": "22" * 32,
            }
        )
        saved = db.save_evm_logs(
            "0xabc",
            [{"topics": [], "data": "0x", "log_index": 0}],
            block_height=2,
            tx_hash="cc" * 32,
        )
        assert saved >= 1
        db.record_tx_propagation_event(
            "cc" * 32,
            "mined",
            peer_id="p1",
            block_height=2,
        )

        with db.atomic():
            db.reorg_truncate_above(1)

        assert db.get_chain_tip() == 1
        assert db.conn.execute("SELECT COUNT(*) AS c FROM evm_logs").fetchone()["c"] == 0
        assert (
            db.conn.execute(
                "SELECT COUNT(*) AS c FROM tx_propagation_events WHERE block_height > 1"
            ).fetchone()["c"]
            == 0
        )
        db.truncate_blocks_above(0)
        assert db.get_chain_tip() == 0
    finally:
        db.close()
        Path(path).unlink(missing_ok=True)
