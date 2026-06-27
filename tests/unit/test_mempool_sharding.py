#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests: mempool API + sharding integration."""

import json
import os
import sys
import threading
import time
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from api.http import create_http_server
from storage.database import Database
from kernel.event_bus import EventBus
from core.blockchain import Blockchain
from blockchain.mempool import Mempool
from dynamic_sharding import ShardingManager


@pytest.fixture
def sharding_config(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "test.db")
    cfg.http_port = 18081
    cfg.rpc_port = 18546
    cfg.p2p_port = 15001
    cfg.deployment_mode = "dev"
    cfg.node_id = "shard-test-node"
    cfg.jwt_enforce_admin = False
    return cfg


@pytest.fixture
def sharding_api(sharding_config):
    db = Database(sharding_config.db_path, synchronous="NORMAL")
    db.initialize()
    bus = EventBus()
    bc = Blockchain(sharding_config, db, bus)
    mp = Mempool(max_size=1000, min_fee=0.001)
    mp.set_blockchain(bc)
    sh = ShardingManager(num_shards=4)
    sh.register_node("shard-test-node")
    server = create_http_server(bc, mp, db, sharding_config, sharding=sh, bus=bus)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.35)
    base = f"http://127.0.0.1:{sharding_config.http_port}"
    yield base, sharding_config, sh, db
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


def test_mempool_audit_empty(sharding_api):
    base, _, _, _ = sharding_api
    status, body = _get(f"{base}/mempool/audit")
    data = json.loads(body)
    assert status == 200
    assert data["stats"]["size"] == 0
    assert data["top_fees"] == []


def test_mempool_endpoint_includes_sharding(sharding_api):
    base, _, _, _ = sharding_api
    status, body = _get(f"{base}/mempool")
    data = json.loads(body)
    assert status == 200
    assert "sharding" in data
    assert data["sharding"]["enabled"] is True
    assert data["sharding"]["total_shards"] == 4


def test_status_includes_mempool_and_sharding(sharding_api):
    base, _, _, _ = sharding_api
    status, body = _get(f"{base}/status")
    data = json.loads(body)
    assert status == 200
    assert "mempool_stats" in data
    assert data["sharding"]["enabled"] is True
    assert data["sharding"]["total_shards"] == 4


def test_tx_send_routes_to_shard_same_shard(sharding_api):
    base, _, sh, db = sharding_api
    addr = "0x" + "c" * 40
    db.set_balance(addr, 50.0)
    body = {"from": addr, "to": addr, "value": 1.0, "nonce": 0}
    status, raw = _post(f"{base}/tx/send", body)
    data = json.loads(raw)
    assert status == 200
    assert data["status"] == "pending"
    assert data["from_shard"] == data["to_shard"]
    assert data["cross_shard"] is False
    assert sh.get_stats()["total_transactions"] >= 1


def _addresses_on_different_shards(sh, num_shards=4):
    """Pick two 0x addresses that hash to different shards."""
    for i in range(200):
        a = f"0x{i:040x}"
        b = f"0x{(i + num_shards * 17):040x}"
        if sh.get_shard_for_address(a) != sh.get_shard_for_address(b):
            return a, b
    raise RuntimeError("could not find cross-shard pair")


def test_tx_send_cross_shard_pending(sharding_api):
    base, _, sh, db = sharding_api
    sender, recipient = _addresses_on_different_shards(sh)
    db.set_balance(sender, 100.0)
    body = {"from": sender, "to": recipient, "value": 2.0, "nonce": 0}
    status, raw = _post(f"{base}/tx/send", body)
    data = json.loads(raw)
    assert status == 200
    assert data["cross_shard"] is True
    assert data["cross_shard_tx_id"]
    pending_status, pending_body = _get(f"{base}/sharding/pending")
    pending = json.loads(pending_body)
    assert pending_status == 200
    assert pending["count"] >= 1
    ids = [p["tx_id"] for p in pending["pending"]]
    assert data["cross_shard_tx_id"] in ids


def test_sharding_stats_enabled_flag(sharding_api):
    base, _, _, _ = sharding_api
    status, body = _get(f"{base}/sharding/stats")
    data = json.loads(body)
    assert status == 200
    assert data["enabled"] is True
    assert len(data["shard_details"]) == 4
