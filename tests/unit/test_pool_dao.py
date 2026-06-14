#!/usr/bin/env python3
"""Pool locks DAO vote and recent transactions API."""
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from runtime.pool_locks import PoolLockManager
from storage.database import Database
from core.blockchain import Blockchain
from blockchain.mempool import Mempool
from api.http import RESTHandler, ThreadedHTTPServer, configure_rate_limiter
from consensus.validator_registry import ValidatorRegistry


def _post(url: str, data: dict, timeout: float = 5):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def _get(url: str, timeout: float = 5):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def _start_server(bc, mp, db, cfg, pool_locks=None, validator_registry=None):
    RESTHandler.blockchain = bc
    RESTHandler.mempool = mp
    RESTHandler.db = db
    RESTHandler.config = cfg
    RESTHandler.wallet = None
    RESTHandler.pool_locks = pool_locks
    RESTHandler.validator_registry = validator_registry
    configure_rate_limiter(cfg)
    port = 18082
    server = ThreadedHTTPServer(("127.0.0.1", port), RESTHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    return f"http://127.0.0.1:{port}", server


def test_dao_vote_unlocks_ecosystem_pool():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    miner = "0xminer000000000000000000000000000001"
    cfg = Config()
    cfg.db_path = path
    cfg.rate_limit_rpm = 0
    cfg.miner_address = miner
    cfg.founder_address = miner
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    pl = PoolLockManager(db, miner)
    vr = ValidatorRegistry()
    vr.register_validator(miner, 1000)
    mp = Mempool(cfg, db)
    base, server = _start_server(bc, mp, db, cfg, pool_locks=pl, validator_registry=vr)
    try:
        st, before = _get(f"{base}/pools/locks")
        assert st == 200
        eco = next(p for p in before["pools"] if p["id"] == "ecosystem")
        assert eco["spendable"] == 0
        st, vote = _post(f"{base}/pools/dao/vote", {"pool_id": "ecosystem", "voter": miner})
        assert st == 200
        assert vote["success"] is True
        assert vote["quorum_reached"] is True
        st, after = _get(f"{base}/pools/locks")
        eco2 = next(p for p in after["pools"] if p["id"] == "ecosystem")
        assert eco2["spendable"] > 0
        assert eco2["dao_unlocked"] is True
    finally:
        server.shutdown()
        db.close()
        os.remove(path)


def test_recent_transactions_endpoint():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.rate_limit_rpm = 0
    cfg.miner_address = "0xminer000000000000000000000000000001"
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    db.save_bridge_lock(
        cfg.miner_address, "ethereum", "0x0001", 9.9, "bridgehash01"
    )
    db.conn.execute(
        """INSERT INTO transactions
           (hash, from_addr, to_addr, value, fee, block_height, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("abc123", cfg.miner_address, "0xdead", 10.0, 0.1, 1, "confirmed"),
    )
    db.conn.commit()
    base, server = _start_server(bc, mp, db, cfg)
    try:
        st, body = _get(f"{base}/transactions/recent?limit=10")
        assert st == 200
        assert body["count"] >= 2
        types = {t.get("type") for t in body["transactions"]}
        assert "transfer" in types
        assert "bridge_lock" in types
    finally:
        server.shutdown()
        db.close()
        os.remove(path)
