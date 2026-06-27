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
from api.http import _handle_call_tx, _handle_deploy_tx, _handle_send_tx_with_wallet
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
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = __file__
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
    RESTHandler.cross_bridge = None
    RESTHandler.p2p = None
    configure_rate_limiter(cfg)
    server = ThreadedHTTPServer(("127.0.0.1", cfg.http_port), RESTHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.25)
    base = f"http://127.0.0.1:{cfg.http_port}"
    return base, server, db, path


def _start_dev_admin_server(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-dev-admin")
    fd, path = tempfile.mkstemp(suffix=".db", dir=tmp_path)
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.http_port = _free_port()
    cfg.deployment_mode = "dev"
    cfg.jwt_enforce_admin = True
    cfg.bridge_enabled = False
    cfg.rate_limit_rpm = 0
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)
    RESTHandler.blockchain = bc
    RESTHandler.mempool = mp
    RESTHandler.db = db
    RESTHandler.config = cfg
    RESTHandler.wallet = None
    RESTHandler.bridge = None
    RESTHandler.p2p = None
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
        assert st == 403
        assert "production" in body.get("error", "")
    finally:
        server.shutdown()
        db.close()
        os.remove(path)


def test_dev_admin_sync_reconcile_requires_jwt(tmp_path, monkeypatch):
    base, server, db, path = _start_dev_admin_server(tmp_path, monkeypatch)
    try:
        st, body = _post(f"{base}/sync/reconcile", {"timeout": 30})
        assert st == 401
        assert "JWT" in body.get("error", "")

        st, token_body = _get(f"{base}/auth/token?address=verifier-admin")
        assert st == 200
        token = token_body["token"]
        st, _body = _post(
            f"{base}/sync/reconcile",
            {"timeout": 30},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert st != 401
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


def test_prod_blocks_dev_and_testnet_endpoints(tmp_path, monkeypatch):
    base, server, db, path = _start_prod_server(tmp_path, monkeypatch)
    try:
        for endpoint in (
            "/devnet/faucet",
            "/testnet/mesh",
            "/chain/consistency/harness",
        ):
            st, body = _get(f"{base}{endpoint}")
            assert st == 403, endpoint
            assert "production" in body.get("error", "")

        st, body = _post(f"{base}/testnet/reorg-exercise", {})
        assert st == 403
        assert "production" in body.get("error", "")

        for endpoint, payload in (
            ("/pools/spend", {"pool_id": "ecosystem", "to": "0x1", "amount": 1}),
            ("/state/credit", {"address": "0x1", "satoshi": 1}),
            ("/crypto/keygen", {}),
            ("/crypto/sign", {"private_key": "00", "transaction": {"nonce": 0}}),
            ("/tx/sign", {"private_key": "00", "from": "0x1", "to": "0x2", "amount": 1}),
            ("/pq/sphincs/sign", {"private_key": "00", "message": "x"}),
            ("/pq/hybrid-sign", {"private_key": "00", "message": "x"}),
            ("/pq/hybrid-decrypt", {"private_key": "00", "ciphertext": "x"}),
            ("/pq/decapsulate", {"private_key": "00", "ciphertext": "x"}),
            ("/bridge/confirm", {"tx_hash": "0xabc"}),
            ("/bridge/confirm-lock", {"tx_hash": "0xabc"}),
            ("/bridge/refund", {"tx_hash": "0xabc"}),
        ):
            st, body = _post(f"{base}{endpoint}", payload)
            assert st == 403, endpoint
            assert "production" in body.get("error", "")

        st, body = _get(f"{base}/crypto/eth-address")
        assert st == 403
        assert "production" in body.get("error", "")
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


def test_prod_bridge_does_not_fallback_to_simulator(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-wave28")
    fd, path = tempfile.mkstemp(suffix=".db", dir=tmp_path)
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.http_port = _free_port()
    cfg.deployment_mode = "prod"
    cfg.jwt_enforce_admin = False
    cfg.bridge_enabled = True
    cfg.bridge_mode = "rust"
    cfg.bridge_oracle_secret = "oracle-secret-wave28"
    cfg.rate_limit_rpm = 0
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    mp = Mempool(cfg, db)

    class _SimulatorFallback:
        def bridge(self, *_args, **_kwargs):
            return "simulator-tx"

        def confirm_transaction(self, *_args, **_kwargs):
            return True

        def estimate_fee(self, *_args, **_kwargs):
            return 0

    RESTHandler.blockchain = bc
    RESTHandler.mempool = mp
    RESTHandler.db = db
    RESTHandler.config = cfg
    RESTHandler.wallet = None
    RESTHandler.bridge = None
    RESTHandler.cross_bridge = _SimulatorFallback()
    RESTHandler.p2p = None
    configure_rate_limiter(cfg)
    server = ThreadedHTTPServer(("127.0.0.1", cfg.http_port), RESTHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.25)
    try:
        base = f"http://127.0.0.1:{cfg.http_port}"
        st, body = _post(
            f"{base}/bridge2/transfer",
            {
                "from_chain": "absolute",
                "to_chain": "ethereum",
                "from_address": "0x" + "1" * 40,
                "to_address": "0x" + "2" * 40,
                "amount": 1,
            },
        )
        assert st == 503
        assert "RustBridge" in body.get("error", "")
    finally:
        server.shutdown()
        db.close()
        os.remove(path)


def test_prod_rust_bridge_runtime_has_no_simulator(tmp_path):
    path = str(tmp_path / "bridge-prod.db")
    cfg = Config()
    cfg.db_path = path
    cfg.deployment_mode = "prod"
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = __file__
    db = Database(path)
    db.initialize()
    try:
        bridge = RustBridge(cfg, db, None)
        assert bridge._mode == "rust"
        assert bridge._simulator is None
        stats = bridge.get_stats()
        assert stats["dev_simulator_stats"]["enabled"] is False
    finally:
        db.close()


def test_prod_bridge_rejects_simulator_runtime(tmp_path):
    path = str(tmp_path / "bridge-prod-sim.db")
    cfg = Config()
    cfg.db_path = path
    cfg.deployment_mode = "prod"
    cfg.bridge_mode = "simulator"
    db = Database(path)
    db.initialize()
    try:
        with pytest.raises(RuntimeError, match="bridge_mode=rust"):
            RustBridge(cfg, db, None)
    finally:
        db.close()


def test_prod_bridge_incoming_requires_l1_tx_hash(tmp_path):
    path = str(tmp_path / "bridge-prod-l1.db")
    cfg = Config()
    cfg.db_path = path
    cfg.deployment_mode = "prod"
    cfg.bridge_mode = "rust"
    cfg.rust_bridge_path = __file__
    db = Database(path)
    db.initialize()
    try:
        bridge = RustBridge(cfg, db, None)
        result = bridge.confirm_incoming(
            "0xl1missing",
            "0x" + "1" * 40,
            1.0,
            "ethereum",
        )
        assert result["confirmed"] is False
        assert "l1_tx_hash required" in result["error"]
    finally:
        db.close()


def test_prod_rejects_auto_sign_shortcuts():
    cfg = Config()
    cfg.deployment_mode = "prod"

    with pytest.raises(ValueError, match="auto_sign is disabled"):
        _handle_send_tx_with_wallet({"auto_sign": True, "to": "0x" + "1" * 40}, None, None, cfg, None)

    with pytest.raises(ValueError, match="auto_sign is disabled"):
        _handle_deploy_tx({"auto_sign": True, "bytecode": "0x00"}, None, None, cfg, None, None)

    with pytest.raises(ValueError, match="auto_sign is disabled"):
        _handle_call_tx({"auto_sign": True, "to": "0x" + "2" * 40, "data": "0x00"}, None, None, cfg, None)
