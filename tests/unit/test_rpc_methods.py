#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests: JSON-RPC eth_* / net_* methods."""

import json
import os
import sys
import threading
import time
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from api.http import create_rpc_server, JSONRPCHandler
from storage.database import Database
from kernel.event_bus import EventBus
from core.blockchain import Blockchain
from blockchain.mempool import Mempool


@pytest.fixture
def rpc_env(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "rpc.db")
    cfg.rpc_port = 28545
    cfg.http_port = 28080
    cfg.mining_enabled = True
    cfg.chain_id = 77777
    db = Database(cfg.db_path, synchronous="NORMAL")
    db.initialize()
    bus = EventBus()
    bc = Blockchain(cfg, db, bus)
    mp = Mempool(max_size=100, min_fee=0.001)
    server = create_rpc_server(bc, mp, cfg, p2p=None, wallet=None, sync_engine=None)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.25)
    url = f"http://127.0.0.1:{cfg.rpc_port}"
    yield url, bc, mp, cfg
    server.shutdown()


def _rpc(url: str, method: str, params=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read().decode())
    assert "error" not in body, body.get("error")
    return body["result"]


def test_rpc_mining_syncing_mempool(rpc_env):
    url, bc, mp, cfg = rpc_env
    assert _rpc(url, "eth_mining") is True
    assert _rpc(url, "eth_syncing") is False
    assert _rpc(url, "eth_getMempoolSize") == hex(0)
    assert _rpc(url, "net_peerCount") == hex(0)


def test_rpc_block_tx_count(rpc_env):
    url, bc, mp, cfg = rpc_env
    height = bc.get_height()
    count = _rpc(url, "eth_getBlockTransactionCountByNumber", [hex(height)])
    blk = bc.get_block(height)
    expected = len(blk.get("transactions", [])) if blk else 0
    assert int(count, 16) == expected


def test_rpc_rejects_fake_raw_tx(rpc_env):
    url, _, __, ___ = rpc_env
    payload = {"jsonrpc": "2.0", "method": "eth_sendRawTransaction", "params": ["0xdeadbeef"], "id": 1}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read().decode())
    assert "error" in body
