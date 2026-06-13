#!/usr/bin/env python3
"""Wallet + bridge Explorer API smoke checks (no live tx submit)."""
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


def _get(url: str, timeout: float = 5):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def _start_server(bc, mp, db, cfg, wallet=None):
    RESTHandler.blockchain = bc
    RESTHandler.mempool = mp
    RESTHandler.db = db
    RESTHandler.config = cfg
    RESTHandler.wallet = wallet
    RESTHandler.p2p = None
    RESTHandler.evm = None
    RESTHandler.bridge = None
    RESTHandler.cross_bridge = None
    configure_rate_limiter(cfg)
    port = 18080
    server = ThreadedHTTPServer(("127.0.0.1", port), RESTHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    return f"http://127.0.0.1:{port}", server


def test_wallet_status_and_address_history():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.rate_limit_rpm = 0
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    base, server = _start_server(bc, mp, db, cfg, wallet=None)
    try:
        st, body = _get(f"{base}/wallet/status")
        assert st == 200
        assert "signing_enabled" in body
        assert "balance" in body

        addr = "0xabc1234567890123456789012345678901234567890"
        db.update_balance(addr, 100.0)
        st2, acct = _get(f"{base}/address/{addr}")
        assert st2 == 200
        assert acct["balance"] == 100.0
        assert acct["nonce"] == 0
    finally:
        server.shutdown()
        db.close()
        os.remove(path)


def test_bridge_overview_manual_confirm():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.bridge_enabled = True
    cfg.bridge_auto_confirm_sec = 0
    cfg.rate_limit_rpm = 0
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    base, server = _start_server(bc, mp, db, cfg)
    try:
        st, body = _get(f"{base}/bridge")
        assert st == 200
        assert body.get("auto_confirm_sec") == 0
        assert "confirm_lock" in (body.get("endpoints") or {})
    finally:
        server.shutdown()
        db.close()
        os.remove(path)
