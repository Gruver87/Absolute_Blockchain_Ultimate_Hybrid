"""GET /chain/consistency/harness HTTP surface (peer_probe_ok, encoding)."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

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


def test_harness_http_peer_probe_ok_and_encoding(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "unit-test-harness-http-secret-32b")
    fd, path = tempfile.mkstemp(suffix=".db", dir=tmp_path)
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.http_port = _free_port()
    cfg.deployment_mode = "prod"
    cfg.jwt_enforce_admin = False
    cfg.rpc_api_key_required = False
    cfg.require_wallet_file = False
    cfg.rate_limit_rpm = 120
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    RESTHandler.config = cfg
    RESTHandler.blockchain = bc
    RESTHandler.mempool = mp
    RESTHandler.db = db
    RESTHandler.p2p = None
    RESTHandler.consensus_adapter = None
    configure_rate_limiter(cfg)
    server = ThreadedHTTPServer(("127.0.0.1", cfg.http_port), RESTHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.25)
    try:
        import json
        import urllib.request

        url = f"http://127.0.0.1:{cfg.http_port}/chain/consistency/harness?quick=1"
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = json.loads(resp.read().decode())
        check_ids = {c["id"]: c["ok"] for c in body.get("checks") or []}
        assert "peer_probe_ok" in check_ids
        assert check_ids["peer_probe_ok"] is True
        enc = (body.get("policy") or {}).get("encoding") or {}
        assert enc.get("active", {}).get("version") == 1
    finally:
        server.shutdown()
        db.close()
        os.remove(path)
