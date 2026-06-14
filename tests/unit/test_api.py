#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests: industrial API surface (health, config, metrics)."""

import json
import os
import sys
import threading
import time
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from observability.metrics import MetricsCollector
from api.http import create_http_server, RESTHandler
from storage.database import Database
from kernel.event_bus import EventBus
from core.blockchain import Blockchain
from blockchain.mempool import Mempool


@pytest.fixture
def industrial_config(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "test.db")
    cfg.http_port = 18080
    cfg.rpc_port = 18545
    cfg.p2p_port = 15000
    cfg.deployment_mode = "dev"
    cfg.node_id = "test-node"
    cfg.metrics_enabled = True
    cfg.jwt_enforce_admin = False
    return cfg


@pytest.fixture
def api_server(industrial_config):
    db = Database(industrial_config.db_path, synchronous="NORMAL")
    db.initialize()
    bus = EventBus()
    bc = Blockchain(industrial_config, db, bus)
    mp = Mempool(max_size=1000, min_fee=0.001)
    server = create_http_server(bc, mp, db, industrial_config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    base = f"http://127.0.0.1:{industrial_config.http_port}"
    yield base, industrial_config
    server.shutdown()


def _get(url: str) -> tuple:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read()


def _post(url: str, payload: dict) -> tuple:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, resp.read()


def test_config_apply_env_prod_wallet_required(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "prod")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cfg = Config()
    cfg.apply_env()
    errors = cfg.validate()
    assert any("wallet" in e for e in errors)
    assert cfg.is_production
    assert cfg.sqlite_synchronous == "FULL"
    assert cfg.enable_cors_rpc_proxy is False


def test_metrics_prometheus_format():
    mc = MetricsCollector()
    text = mc.render_prometheus(height=42, peers=3, mempool=7, node_id="n1")
    assert "abs_chain_height" in text
    assert 'abs_chain_height{node_id="n1"} 42' in text
    assert "abs_uptime_seconds" in text


def test_health_live(api_server):
    base, _ = api_server
    status, body = _get(f"{base}/health/live")
    data = json.loads(body)
    assert status == 200
    assert data["status"] == "alive"
    assert data["node_id"] == "test-node"


def test_health_ready(api_server):
    base, _ = api_server
    status, body = _get(f"{base}/health/ready")
    data = json.loads(body)
    assert status == 200
    assert data["status"] == "ready"
    assert data["checks"]["blockchain"] is True


def test_metrics_endpoint(api_server):
    base, _ = api_server
    status, body = _get(f"{base}/metrics")
    text = body.decode()
    assert status == 200
    assert "abs_chain_height" in text


def test_status_has_health_links(api_server):
    base, _ = api_server
    status, body = _get(f"{base}/status")
    data = json.loads(body)
    assert status == 200
    assert "health" in data
    assert data["health"]["live"] == "/health/live"
    assert data.get("api_docs") == "/docs"
    assert data.get("openapi") == "/openapi.json"
    assert "bridge_pending" in data
    assert "bridge_locks_total" in data
    assert data["bridge_pending"] == 0


def test_status_bridge_pending_counts(api_server, industrial_config):
    base, cfg = api_server
    db = Database(cfg.db_path, synchronous="NORMAL")
    db.save_bridge_lock("0xfrom", "ethereum", "0xto", 5.0, "pending99")
    status, body = _get(f"{base}/status")
    data = json.loads(body)
    assert status == 200
    assert data["bridge_pending"] == 1
    assert data["bridge_locks_total"] == 1


def test_peers_alias(api_server):
    base, _ = api_server
    status, body = _get(f"{base}/peers")
    data = json.loads(body)
    assert status == 200
    assert "peers" in data
    assert "solo_mode" in data
    assert data["count"] == 0
    assert data["solo_mode"] is True


def test_bridge_overview(api_server):
    base, _ = api_server
    status, body = _get(f"{base}/bridge")
    data = json.loads(body)
    assert status == 200
    assert data["enabled"] is True
    assert data["mode"] in ("simulator", "rust")
    assert "locks" in data
    assert "supported_chains" in data


def test_sync_status_real(api_server):
    base, _ = api_server
    status, body = _get(f"{base}/sync/status")
    data = json.loads(body)
    assert status == 200
    assert data["enabled"] is True
    assert "local_height" in data
    assert data["solo_mode"] is True


def test_wallet_status(api_server):
    base, _ = api_server
    status, body = _get(f"{base}/wallet/status")
    data = json.loads(body)
    assert status == 200
    assert "signing_enabled" in data
    assert "miner_address" in data


def test_openapi_spec(api_server):
    base, _ = api_server
    status, body = _get(f"{base}/openapi.json")
    data = json.loads(body)
    assert status == 200
    assert data["openapi"] == "3.0.3"
    assert "/peers" in data["paths"]
    assert "/bridge" in data["paths"]


def test_tx_send_alias(api_server, industrial_config):
    base, cfg = api_server
    db = Database(cfg.db_path, synchronous="NORMAL")
    sender = "0x" + "a" * 40
    recipient = "0x" + "b" * 40
    db.set_balance(sender, 100.0)
    body = {"from": sender, "to": recipient, "value": 1.0, "nonce": 0}
    status, raw = _post(f"{base}/tx/send", body)
    data = json.loads(raw)
    assert status == 200
    assert data["status"] == "pending"
    assert len(data["tx_hash"]) == 64
