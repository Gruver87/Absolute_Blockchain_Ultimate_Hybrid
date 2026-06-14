#!/usr/bin/env python3
"""Devnet faucet and founder balance API."""
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from core.blockchain import Blockchain
from blockchain.mempool import Mempool
from api.http import RESTHandler, ThreadedHTTPServer, configure_rate_limiter


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


def _start_server(bc, mp, db, cfg):
    RESTHandler.blockchain = bc
    RESTHandler.mempool = mp
    RESTHandler.db = db
    RESTHandler.config = cfg
    RESTHandler.wallet = None
    configure_rate_limiter(cfg)
    port = 18081
    server = ThreadedHTTPServer(("127.0.0.1", port), RESTHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    return f"http://127.0.0.1:{port}", server


def test_devnet_faucet_credits_balance():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.deployment_mode = "dev"
    cfg.rate_limit_rpm = 0
    cfg.miner_address = "0xminer000000000000000000000000000001"
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    base, server = _start_server(bc, mp, db, cfg)
    try:
        addr = "0xtestfaucet000000000000000000000001"
        st, body = _post(f"{base}/devnet/faucet", {"address": addr, "amount": 50})
        assert st == 200
        assert body["success"] is True
        assert body["balance"] == 50
    finally:
        server.shutdown()
        db.close()
        os.remove(path)


def test_founder_balance_matches_allocation_address():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.rate_limit_rpm = 0
    cfg.miner_address = "0xminer000000000000000000000000000001"
    db = Database(path)
    db.initialize()
    db.set_balance(cfg.miner_address, 1_000_000.0)
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    base, server = _start_server(bc, mp, db, cfg)
    try:
        st, body = _get(f"{base}/founder")
        assert st == 200
        assert body["address"] == cfg.miner_address
        assert body["balance_abs"] >= 1_000_000.0
    finally:
        server.shutdown()
        db.close()
        os.remove(path)
