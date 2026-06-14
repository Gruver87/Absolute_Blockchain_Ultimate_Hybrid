#!/usr/bin/env python3
"""Production API auth: JWT on admin POSTs, bridge oracle HMAC."""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from core.blockchain import Blockchain
from blockchain.mempool import Mempool
from bridge.abs_bridge import RustBridge
from bridge.oracle_auth import sign_payload
from api.http import RESTHandler, ThreadedHTTPServer, configure_rate_limiter
from kernel.event_bus import EventBus


def _post(url: str, data: dict, headers: dict | None = None, timeout: float = 5):
    body = json.dumps(data).encode()
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _get(url: str, timeout: float = 5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def _start_prod_server(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-wave28")
    monkeypatch.setenv("BRIDGE_ORACLE_SECRET", "oracle-secret-wave28")
    fd, path = tempfile.mkstemp(suffix=".db", dir=tmp_path)
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.http_port = _free_port()
    cfg.deployment_mode = "prod"
    cfg.jwt_enforce_admin = True
    cfg.bridge_enabled = True
    cfg.bridge_mode = "simulator"
    cfg.bridge_oracle_secret = "oracle-secret-wave28"
    cfg.rate_limit_rpm = 0
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    bus = EventBus()
    bridge = RustBridge(cfg, db, bus)
    RESTHandler.blockchain = bc
    RESTHandler.mempool = mp
    RESTHandler.db = db
    RESTHandler.config = cfg
    RESTHandler.wallet = None
    RESTHandler.bridge = bridge
    configure_rate_limiter(cfg)
    server = ThreadedHTTPServer(("127.0.0.1", cfg.http_port), RESTHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.25)
    base = f"http://127.0.0.1:{cfg.http_port}"
    return base, server, db, path


def test_prod_bridge_confirm_lock_requires_jwt(tmp_path, monkeypatch):
    base, server, db, path = _start_prod_server(tmp_path, monkeypatch)
    try:
        st, body = _post(f"{base}/bridge/confirm-lock", {"tx_hash": "0xabc"})
        assert st == 401
        assert "JWT" in body.get("error", "")
    finally:
        server.shutdown()
        db.close()
        os.remove(path)


def test_prod_oracle_confirm_lock_with_hmac(tmp_path, monkeypatch):
    base, server, db, path = _start_prod_server(tmp_path, monkeypatch)
    try:
        payload = {"tx_hash": "0xnonexistent"}
        raw = json.dumps(payload).encode()
        sig = sign_payload("oracle-secret-wave28", raw)
        st, body = _post(
            f"{base}/bridge/oracle/confirm-lock",
            payload,
            headers={"X-Bridge-Oracle-Signature": sig},
        )
        assert st in (200, 404, 501)
    finally:
        server.shutdown()
        db.close()
        os.remove(path)


def test_prod_auth_token_get_disabled(tmp_path, monkeypatch):
    base, server, db, path = _start_prod_server(tmp_path, monkeypatch)
    try:
        st, body = _get(f"{base}/auth/token?address=0x1")
        assert st == 403
    finally:
        server.shutdown()
        db.close()
        os.remove(path)


def test_status_includes_security_flags(tmp_path, monkeypatch):
    base, server, db, path = _start_prod_server(tmp_path, monkeypatch)
    try:
        st, body = _get(f"{base}/status")
        assert st == 200
        assert body["deployment_mode"] == "prod"
        assert body["jwt_enforce_admin"] is True
        assert body["bridge_oracle_enabled"] is True
    finally:
        server.shutdown()
        db.close()
        os.remove(path)
