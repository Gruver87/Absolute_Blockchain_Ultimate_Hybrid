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


def test_founder_balance_fallback_to_miner_wallet():
    from runtime.tokenomics import DEFAULT_FOUNDER_ADDRESS, founder_balance_lookup

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    miner = "0xminer000000000000000000000000000001"
    db = Database(path)
    db.initialize()
    db.set_meta("genesis_alloc_applied", True)
    db.set_balance(miner, 250_000.0)
    try:
        info = founder_balance_lookup(db, DEFAULT_FOUNDER_ADDRESS, miner)
        assert info["address"] == DEFAULT_FOUNDER_ADDRESS
        assert info["balance_abs"] == 250_000.0
        assert info["balance_address"] == miner
    finally:
        db.close()
        os.remove(path)


def test_genesis_allocation_applies_founder_pool():
    from runtime.tokenomics import DEFAULT_FOUNDER_ADDRESS, FOUNDER_AMOUNT_ABS

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.founder_address = DEFAULT_FOUNDER_ADDRESS
    cfg.miner_address = "0xminer000000000000000000000000000001"
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    from main import NodeOrchestrator

    orch = object.__new__(NodeOrchestrator)
    orch.config = cfg
    orch.db = db
    orch._apply_genesis_allocation()
    try:
        bal = db.get_balance(DEFAULT_FOUNDER_ADDRESS)
        assert bal >= FOUNDER_AMOUNT_ABS * 0.99
        assert db.get_meta("genesis_alloc_applied")
    finally:
        db.close()
        os.remove(path)
