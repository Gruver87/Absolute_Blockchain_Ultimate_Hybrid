"""Mock L1 JSON-RPC server tests."""
import json
import os
import sys
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from bridge import l1_rpc
from bridge.mock_l1_rpc import register_confirmed_tx, start_mock_l1_rpc, clear_mock_registry


@pytest.fixture
def mock_rpc():
    clear_mock_registry()
    server, url = start_mock_l1_rpc(port=19445)
    yield url, server
    server.shutdown()
    clear_mock_registry()


def test_mock_l1_confirms_tx(mock_rpc):
    url, _server = mock_rpc
    tx = "0x" + "aa" * 32
    register_confirmed_tx(tx, block_number=100, head_block=120)
    assert l1_rpc.is_tx_confirmed(url, tx, required=1) is True
    assert l1_rpc.is_tx_confirmed(url, "0x" + "bb" * 32, required=1) is False


def test_mock_l1_json_rpc_shape(mock_rpc):
    url, _server = mock_rpc
    tx = "0x" + "cc" * 32
    register_confirmed_tx(tx)
    payload = json.dumps(
        {"jsonrpc": "2.0", "method": "eth_getTransactionReceipt", "params": [tx], "id": 1}
    ).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
    assert data.get("result", {}).get("blockNumber")
