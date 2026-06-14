#!/usr/bin/env python3
"""Bridge incoming credit API (simulator mode)."""
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
    port = 18085
    server = ThreadedHTTPServer(("127.0.0.1", port), RESTHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    return f"http://127.0.0.1:{port}", server


def test_bridge_incoming_credits_recipient():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    recipient = "0xrecipient000000000000000000000001"
    cfg = Config()
    cfg.db_path = path
    cfg.rate_limit_rpm = 0
    cfg.deployment_mode = "dev"
    cfg.bridge_enabled = True
    cfg.bridge_mode = "simulator"
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    bridge = RustBridge(cfg, db, EventBus())
    base, server = _start_server(bc, mp, db, cfg, bridge)
    try:
        st, body = _post(f"{base}/bridge/confirm", {
            "tx_id": "incoming01",
            "recipient": recipient,
            "amount": 42.5,
            "from_chain": "ethereum",
        })
        assert st == 200
        assert body.get("confirmed") is True
        assert db.get_balance(recipient) == 42.5
    finally:
        server.shutdown()
        db.close()
        os.remove(path)
