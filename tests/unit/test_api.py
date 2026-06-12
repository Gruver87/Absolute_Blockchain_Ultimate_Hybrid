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
