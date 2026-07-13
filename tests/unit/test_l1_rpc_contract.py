#!/usr/bin/env python3
"""L1 RPC helpers — contract bytecode probe (eth_getCode)."""

from bridge import l1_rpc


def test_get_contract_code_returns_bytecode(monkeypatch):
    def fake_rpc(_url, method, params, timeout=15):
        assert method == "eth_getCode"
        assert params[0] == "0x" + "11" * 20
        return "0x6080604052"

    monkeypatch.setattr(l1_rpc, "_rpc_call", fake_rpc)
    code = l1_rpc.get_contract_code("https://rpc.example.com", "0x" + "11" * 20)
    assert code == "0x6080604052"


def test_get_contract_code_empty_on_rpc_error(monkeypatch):
    def fake_rpc(*_args, **_kwargs):
        raise RuntimeError("rpc down")

    monkeypatch.setattr(l1_rpc, "_rpc_call", fake_rpc)
    assert l1_rpc.get_contract_code("https://rpc.example.com", "0x" + "22" * 20) == "0x"


def test_get_contract_code_empty_without_url_or_address():
    assert l1_rpc.get_contract_code("", "0x" + "11" * 20) == "0x"
    assert l1_rpc.get_contract_code("https://rpc.example.com", "") == "0x"
