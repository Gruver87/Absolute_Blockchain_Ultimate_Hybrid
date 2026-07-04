#!/usr/bin/env python3
"""Status API exposes hybrid consensus telemetry."""

import json
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from kernel.event_bus import EventBus
from core.blockchain import Blockchain
from consensus.adapter import ConsensusAdapter
from api.http import RESTHandler, ThreadedHTTPServer, configure_rate_limiter


def test_status_includes_hybrid_consensus_fields():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.deployment_mode = "prod"
    cfg.consensus_mode = "unified"
    cfg.http_port = 15380
    cfg.rate_limit_rpm = 0
    cfg.jwt_enforce_admin = False
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())
    adapter = ConsensusAdapter(cfg, db, EventBus())
    bc.consensus_adapter = adapter

    RESTHandler.blockchain = bc
    RESTHandler.db = db
    RESTHandler.config = cfg
    RESTHandler.consensus_adapter = adapter
    RESTHandler.p2p = None
    RESTHandler.mempool = __import__("blockchain.mempool", fromlist=["Mempool"]).Mempool(cfg, db)
    configure_rate_limiter(cfg)

    server = ThreadedHTTPServer(("127.0.0.1", cfg.http_port), RESTHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    try:
        import urllib.request

        with urllib.request.urlopen(f"http://127.0.0.1:{cfg.http_port}/status", timeout=5) as resp:
            st = json.loads(resp.read().decode())
        assert st["deployment_mode"] == "prod"
        assert st["state_root_strict_p2p"] is True
        assert st.get("head_hash")
        cons = st.get("consensus") or {}
        assert cons.get("mode") == "unified"
        assert cons.get("unified_path") is True
        assert cons.get("lmd_ghost_enabled") is True
    finally:
        server.shutdown()
        db.close()
        try:
            os.remove(path)
        except OSError:
            pass
