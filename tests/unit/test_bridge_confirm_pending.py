#!/usr/bin/env python3
"""Batch bridge lock confirmation API."""
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
from bridge.abs_bridge import RustBridge
from api.http import RESTHandler, ThreadedHTTPServer, configure_rate_limiter
from kernel.event_bus import EventBus


def _post(url: str, data: dict, timeout: float = 5):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def _start_server(bc, mp, db, cfg, bridge):
    RESTHandler.blockchain = bc
    RESTHandler.mempool = mp
    RESTHandler.db = db
    RESTHandler.config = cfg
    RESTHandler.wallet = None
    RESTHandler.bridge = bridge
    configure_rate_limiter(cfg)
    port = 18084
    server = ThreadedHTTPServer(("127.0.0.1", port), RESTHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    return f"http://127.0.0.1:{port}", server


def test_confirm_pending_locks_batch():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.rate_limit_rpm = 0
    cfg.deployment_mode = "dev"
    cfg.bridge_enabled = True
    cfg.bridge_mode = "simulator"
    cfg.miner_address = "0xminer000000000000000000000000000001"
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    bus = EventBus()
    bridge = RustBridge(cfg, db, bus)
    db.save_bridge_lock("0xminer", "ethereum", "0x1", 5.0, "pending01")
    db.save_bridge_lock("0xminer", "ethereum", "0x2", 7.0, "pending02")
    db.confirm_bridge_lock("pending02")
    base, server = _start_server(bc, mp, db, cfg, bridge)
    try:
        st, body = _post(f"{base}/bridge/confirm-pending", {})
        assert st == 200
        assert body["count"] == 1
        assert "pending01" in body["confirmed"]
        locks = db.get_bridge_locks()
        assert all(l["status"] == "confirmed" for l in locks)
    finally:
        server.shutdown()
        db.close()
        os.remove(path)
