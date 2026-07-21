#!/usr/bin/env python3
"""GET /status honesty — core_real and rate limit backend."""

import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import api.http as http_module
from runtime.config import Config
from storage.database import Database
from core.blockchain import Blockchain
from blockchain.mempool import Mempool
from api.http import RESTHandler, ThreadedHTTPServer, configure_rate_limiter


def _free_port():
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_status_core_real_honest_when_bridge_off(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "unit-test-status-honesty-secret-32b")
    fd, path = tempfile.mkstemp(suffix=".db", dir=tmp_path)
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.http_port = _free_port()
    cfg.deployment_mode = "prod"
    cfg.bridge_enabled = False
    cfg.bridge_mode = "rust"
    cfg.jwt_enforce_admin = False
    cfg.rpc_api_key_required = False
    cfg.rate_limit_rpm = 100_000
    cfg.require_wallet_file = False
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    RESTHandler.config = cfg
    RESTHandler.blockchain = bc
    RESTHandler.mempool = mp
    RESTHandler.db = db
    RESTHandler.wallet = None
    RESTHandler.bridge = None
    RESTHandler.cross_bridge = None
    RESTHandler.p2p = None
    RESTHandler.consensus_adapter = None
    RESTHandler.project_root = os.path.dirname(os.path.dirname(os.path.abspath(http_module.__file__)))
    configure_rate_limiter(cfg)
    server = ThreadedHTTPServer(("127.0.0.1", cfg.http_port), RESTHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.25)
    try:
        import urllib.request
        import json

        with urllib.request.urlopen(f"http://127.0.0.1:{cfg.http_port}/status", timeout=10) as resp:
            body = json.loads(resp.read().decode())
        core = body.get("core_real") or {}
        assert core.get("bridge_relayer_live") is False
        assert core.get("bridge_production_path") is False
        assert "note" in core
        mw = body.get("middleware") or {}
        assert "rate_limit_backend" in mw
        assert body.get("p2p_hardening") is not None
        srp = body.get("state_root_policy") or {}
        enc = (srp.get("encoding") or {}).get("active") or {}
        assert enc.get("version") == 1
        assert enc.get("name") == "float_b_round12"
    finally:
        server.shutdown()
        db.close()
        os.remove(path)
