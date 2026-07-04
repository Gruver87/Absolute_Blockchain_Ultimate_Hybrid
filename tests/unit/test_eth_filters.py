#!/usr/bin/env python3
"""eth_newFilter / eth_getFilterChanges JSON-RPC polling."""

import json
import os
import sys
import threading
import time
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from api.http import create_rpc_server, _handle_eth_get_logs
from api.eth_filters import EthFilterStore
from storage.database import Database
from kernel.event_bus import EventBus
from core.blockchain import Blockchain
from blockchain.mempool import Mempool, MempoolTransaction


@pytest.fixture
def filter_rpc_env(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "filters.db")
    cfg.rpc_port = 28546
    cfg.http_port = 28081
    cfg.mining_enabled = True
    cfg.miner_address = "0x" + "11" * 20
    db = Database(cfg.db_path, synchronous="NORMAL")
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())
    mp = Mempool(max_size=100, min_fee=0.001)
    server = create_rpc_server(bc, mp, cfg)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.25)
    url = f"http://127.0.0.1:{cfg.rpc_port}"
    yield url, bc, mp, cfg
    server.shutdown()


def _rpc(url, method, params=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params or [], "id": 1}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read().decode())
    assert "error" not in body, body.get("error")
    return body["result"]


def test_eth_log_filter_rpc(filter_rpc_env):
    url, bc, mp, cfg = filter_rpc_env
    contract = "0x" + "ef" * 20
    filt_id = _rpc(
        url,
        "eth_newFilter",
        [{"fromBlock": "0x0", "toBlock": "latest", "address": contract}],
    )
    assert filt_id.startswith("0x")
    assert _rpc(url, "eth_getFilterChanges", [filt_id]) == []

    assert bc.add_block(bc.create_block([], cfg.miner_address)) is True
    new_h = bc.get_height()
    bc.db.save_evm_logs(
        contract,
        [{"topics": ["0xfeed"], "data": "face"}],
        block_height=new_h,
        tx_hash="0xabc",
    )

    logs = _rpc(url, "eth_getFilterChanges", [filt_id])
    assert len(logs) == 1
    assert logs[0]["address"].lower() == contract.lower()

    all_logs = _rpc(url, "eth_getFilterLogs", [filt_id])
    assert len(all_logs) == 1
    assert _rpc(url, "eth_uninstallFilter", [filt_id]) is True
    assert _rpc(url, "eth_getFilterChanges", [filt_id]) == []


def test_eth_block_and_pending_filters(filter_rpc_env):
    url, bc, mp, cfg = filter_rpc_env
    block_id = _rpc(url, "eth_newBlockFilter")
    pending_id = _rpc(url, "eth_newPendingTransactionFilter")

    assert bc.add_block(bc.create_block([], cfg.miner_address)) is True
    hashes = _rpc(url, "eth_getFilterChanges", [block_id])
    assert len(hashes) == 1
    assert hashes[0].startswith("0x")

    tx = MempoolTransaction(
        "0x" + "aa" * 32,
        "0x" + "aa" * 20,
        "0x" + "bb" * 20,
        1.0,
        0.01,
        signature="aa",
        public_key="bb" * 32,
    )
    assert mp.add(tx, signature_preverified=True) is True
    pending = _rpc(url, "eth_getFilterChanges", [pending_id])
    assert len(pending) == 1
    assert pending[0] == tx.tx_hash
    assert _rpc(url, "eth_getFilterChanges", [pending_id]) == []


def test_eth_filter_store_unit(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "unit_filters.db")
    cfg.miner_address = "0x" + "11" * 20
    db = Database(cfg.db_path, synchronous="NORMAL")
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())
    mp = Mempool(max_size=10, min_fee=0.001)
    store = EthFilterStore()
    contract = "0x" + "cd" * 20

    filt_id = store.new_log_filter({"address": contract}, bc)
    assert bc.add_block(bc.create_block([], cfg.miner_address)) is True
    h = bc.get_height()
    db.save_evm_logs(
        contract,
        [{"topics": ["0x01"], "data": "02"}],
        block_height=h,
        tx_hash="0xtx",
    )
    logs = store.get_filter_changes(filt_id, bc, mp, _handle_eth_get_logs)
    assert len(logs) == 1
    assert store.get_filter_changes(filt_id, bc, mp, _handle_eth_get_logs) == []
    assert store.uninstall(filt_id) is True
