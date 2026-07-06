#!/usr/bin/env python3
"""RocksDB tx propagation trace read path on hybrid prod store."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from runtime.config import Config
from storage.hybrid_database import HybridDatabase


@pytest.fixture
def hybrid_db(tmp_path):
    try:
        import abs_native  # noqa: F401
    except ImportError:
        pytest.skip("abs_native not built")
    cfg = Config()
    cfg.db_path = str(tmp_path / "chainstore")
    cfg.db_engine = "rocksdb"
    db = HybridDatabase(cfg)
    db.initialize()
    yield db
    db.close()


def test_tx_propagation_trace_on_rocks(hybrid_db):
    tx = "0xabc123"
    hybrid_db.record_tx_propagation_event(tx, "api_submit", node_id="node-a")
    hybrid_db.record_tx_propagation_event(tx, "mempool_local", node_id="node-a")
    hybrid_db.record_tx_propagation_event(tx, "p2p_broadcast", node_id="node-a", detail={"peer_count": 1})
    trace = hybrid_db.get_tx_propagation_trace(tx)
    assert len(trace["events"]) == 3
    assert trace["status"] == "mempool"
    assert trace["events"][0]["stage"] == "api_submit"


def test_recent_tx_propagation_on_rocks(hybrid_db):
    hybrid_db.record_tx_propagation_event("0x111", "api_submit", node_id="n1")
    hybrid_db.record_tx_propagation_event("0x222", "api_submit", node_id="n1")
    hybrid_db.record_tx_propagation_event("0x111", "mempool_local", node_id="n1")
    recent = hybrid_db.get_recent_tx_propagation(limit=5)
    hashes = {row["tx_hash"] for row in recent}
    assert "0x111" in hashes
    assert "0x222" in hashes
