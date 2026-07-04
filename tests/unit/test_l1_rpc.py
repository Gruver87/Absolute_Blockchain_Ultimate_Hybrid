#!/usr/bin/env python3
"""L1 RPC helper tests."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from bridge import l1_rpc


def test_chain_rpc_url_from_env(monkeypatch):
    monkeypatch.setenv("ETH_RPC_URL", "https://eth.example")
    assert l1_rpc.chain_rpc_url("ethereum") == "https://eth.example"
    monkeypatch.delenv("ETH_RPC_URL", raising=False)
    assert l1_rpc.chain_rpc_url("ethereum") == ""


def test_load_save_l1_queue(tmp_path):
    path = str(tmp_path / "queue.json")
    l1_rpc.save_l1_queue(path, {"outbound": [{"abs_tx_hash": "0x1"}], "incoming": []})
    data = l1_rpc.load_l1_queue(path)
    assert len(data["outbound"]) == 1
    assert data["incoming"] == []


def test_is_tx_confirmed_mock(monkeypatch):
    calls = []

    def fake_rpc(url, method, params, timeout=15):
        calls.append(method)
        if method == "eth_getTransactionReceipt":
            return {"blockNumber": "0x64"}
        if method == "eth_blockNumber":
            return "0x6e"
        return None

    monkeypatch.setattr(l1_rpc, "_rpc_call", fake_rpc)
    assert l1_rpc.get_tx_confirmations("http://rpc", "0xabc") == 11
    assert l1_rpc.is_tx_confirmed("http://rpc", "0xabc", required=10) is True
    assert l1_rpc.is_tx_confirmed("http://rpc", "0xabc", required=12) is False


def test_get_tx_confirmations_pending(monkeypatch):
    monkeypatch.setattr(l1_rpc, "_rpc_call", lambda *a, **k: None)
    assert l1_rpc.get_tx_confirmations("http://rpc", "0xabc") == 0


def test_probe_l1_rpc_url_ok(monkeypatch):
    monkeypatch.setattr(l1_rpc, "_rpc_call", lambda url, method, params, timeout=15: "0x2a")
    probe = l1_rpc.probe_l1_rpc_url("http://rpc")
    assert probe["ok"] is True
    assert probe["block_number"] == 42


def test_probe_configured_l1_rpcs_partial_failure(monkeypatch):
    monkeypatch.setenv("ETH_RPC_URL", "http://eth")
    monkeypatch.setenv("BSC_RPC_URL", "http://bsc")
    monkeypatch.delenv("POLYGON_RPC_URL", raising=False)

    def fake_rpc(url, method, params, timeout=15):
        if url == "http://eth":
            return "0x10"
        raise RuntimeError("offline")

    monkeypatch.setattr(l1_rpc, "_rpc_call", fake_rpc)
    result = l1_rpc.probe_configured_l1_rpcs()
    assert result["ok"] is False
    assert result["probes"]["ETH_RPC_URL"]["ok"] is True
    assert "offline" in result["probes"]["BSC_RPC_URL"]["error"]
