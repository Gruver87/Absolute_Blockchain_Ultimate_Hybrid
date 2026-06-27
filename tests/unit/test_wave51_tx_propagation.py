"""Wave 51 — real tx propagation across P2P with SQLite trace."""
import os
import sys
import tempfile
import threading
import time
import json
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def test_propagation_trace_stages():
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "t.db"))
    db.initialize()
    tx = "0xabc123"
    db.record_tx_propagation_event(tx, "api_submit", node_id="node-a")
    db.record_tx_propagation_event(tx, "mempool_local", node_id="node-a")
    db.record_tx_propagation_event(tx, "p2p_broadcast", node_id="node-a", detail={"peer_count": 1})
    db.record_tx_propagation_event(tx, "p2p_received", node_id="node-b", peer_id="peer-1")
    db.record_tx_propagation_event(tx, "mempool_remote", node_id="node-b")
    trace = db.get_tx_propagation_trace(tx)
    assert len(trace["events"]) == 5
    assert trace["status"] == "mempool"


def test_block_confirm_updates_trace():
    from core.blockchain import Blockchain, Transaction
    from runtime.config import Config
    from storage.database import Database
    from kernel.event_bus import EventBus

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "c.db"))
    db.initialize()
    cfg = Config()
    miner = "0x" + "a" * 40
    cfg.miner_address = miner
    cfg.burn_address = "0x" + "d" * 40
    db.update_balance(miner, 10_000.0)
    bc = Blockchain(cfg, db, EventBus())
    tx = Transaction(from_addr=miner, to_addr="0x" + "b" * 40, value=1.0, nonce=0)
    block = bc.create_block([tx], miner)
    assert bc.add_block(block) is True
    trace = db.get_tx_propagation_trace(tx.hash)
    stages = [e["stage"] for e in trace["events"]]
    assert "block_included" in stages
    assert "block_confirmed" in stages
    assert trace["status"] == "confirmed"


def test_mempool_wire_roundtrip():
    from blockchain.mempool import Mempool, MempoolTransaction
    from blockchain.mempool_wire import mempool_tx_to_wire

    mp = Mempool()
    tx = MempoolTransaction(
        tx_hash="0xwire1",
        from_addr="0x" + "1" * 40,
        to_addr="0x" + "2" * 40,
        amount=3.5,
        fee=0.01,
        nonce=0,
        signature="0xsig",
        public_key="0xpub",
        data="0x",
        gas=21000,
    )
    wire = mempool_tx_to_wire(tx)
    assert wire["hash"] == "0xwire1"
    assert wire["signature"] == "0xsig"
    assert mp.add_raw(tx)
    got = mp.get_transaction("0xwire1")
    assert got is not None
    assert got.amount == 3.5


def test_api_submit_records_trace():
    import json as _json
    from runtime.config import Config
    from storage.database import Database
    from core.blockchain import Blockchain
    from blockchain.mempool import Mempool
    from api.http import RESTHandler, ThreadedHTTPServer, _handle_send_tx_obj

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.rate_limit_rpm = 0
    cfg.require_signatures = False
    cfg.node_id = "test-node"
    db = Database(path)
    db.initialize()
    sender = "0x" + "e" * 40
    db.update_balance(sender, 100.0)
    bc = Blockchain(cfg, db)
    mp = Mempool()
    mp.set_blockchain(bc)
    RESTHandler.blockchain = bc
    RESTHandler.mempool = mp
    RESTHandler.db = db
    RESTHandler.config = cfg
    tx_hash = _handle_send_tx_obj({
        "from": sender,
        "to": "0x" + "f" * 40,
        "value": 1.0,
        "nonce": 0,
        "gas": 21000,
    }, bc, mp, cfg)
    trace = db.get_tx_propagation_trace(tx_hash)
    stages = [e["stage"] for e in trace["events"]]
    assert "api_submit" in stages
    assert "mempool_local" in stages
    db.close()
    os.remove(path)
