#!/usr/bin/env python3
"""eth_getLogs filter + receipt logs."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from storage.database import Database


def test_query_evm_logs_block_and_topic_filter(tmp_path):
    db = Database(str(tmp_path / "logs.db"))
    db.initialize()
    contract = "0x" + "aa" * 20
    other = "0x" + "bb" * 20
    db.save_evm_logs(
        contract,
        [{"topics": ["0x1111"], "data": "dead"}],
        block_height=5,
        tx_hash="0xtx1",
    )
    db.save_evm_logs(
        contract,
        [{"topics": ["0x2222"], "data": "beef"}],
        block_height=8,
        tx_hash="0xtx2",
    )
    db.save_evm_logs(
        other,
        [{"topics": ["0x1111"], "data": "cafe"}],
        block_height=6,
        tx_hash="0xtx3",
    )

    rows = db.query_evm_logs(from_block=5, to_block=7, addresses=[contract])
    assert len(rows) == 1
    assert rows[0]["data"] == "dead"

    rows = db.query_evm_logs(
        from_block=0,
        to_block=99,
        topics=["0x1111"],
    )
    assert len(rows) == 2

    rows = db.query_evm_logs(
        from_block=0,
        to_block=99,
        topics=[["0x1111", "0x9999"]],
    )
    assert len(rows) == 2

    rows = db.query_evm_logs(
        from_block=0,
        to_block=99,
        topics=["0x2222"],
    )
    assert len(rows) == 1
    assert rows[0]["tx_hash"] == "0xtx2"


def test_get_evm_logs_by_tx(tmp_path):
    db = Database(str(tmp_path / "txlogs.db"))
    db.initialize()
    contract = "0x" + "cc" * 20
    db.save_evm_logs(
        contract,
        [{"topics": ["0x01"], "data": "11"}, {"topics": ["0x02"], "data": "22"}],
        block_height=3,
        tx_hash="0xabc",
    )
    rows = db.get_evm_logs_by_tx("0xabc")
    assert len(rows) == 2
    assert rows[0]["data"] == "11"
    assert rows[1]["data"] == "22"
