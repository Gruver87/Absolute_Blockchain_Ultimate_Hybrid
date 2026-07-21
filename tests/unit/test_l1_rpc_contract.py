#!/usr/bin/env python3
"""L1 RPC helpers — contract bytecode probe (eth_getCode)."""

import pytest

from bridge import l1_rpc


def test_get_contract_code_returns_bytecode(monkeypatch):
    def fake_rpc(_url, method, params, timeout=15):
        assert method == "eth_getCode"
        assert params[0] == "0x" + "11" * 20
        return "0x6080604052"

    monkeypatch.setattr(l1_rpc, "_rpc_call", fake_rpc)
    code = l1_rpc.get_contract_code("https://rpc.example.com", "0x" + "11" * 20)
    assert code == "0x6080604052"


def test_get_contract_code_raises_on_rpc_error_fail_closed(monkeypatch):
    def fake_rpc(*_args, **_kwargs):
        raise RuntimeError("rpc down")

    monkeypatch.setattr(l1_rpc, "_rpc_call", fake_rpc)
    with pytest.raises(RuntimeError, match="eth_getCode failed"):
        l1_rpc.get_contract_code("https://rpc.example.com", "0x" + "22" * 20)


def test_get_contract_code_soft_mode_returns_empty_on_rpc_error(monkeypatch):
    def fake_rpc(*_args, **_kwargs):
        raise RuntimeError("rpc down")

    monkeypatch.setattr(l1_rpc, "_rpc_call", fake_rpc)
    assert (
        l1_rpc.get_contract_code(
            "https://rpc.example.com", "0x" + "22" * 20, fail_closed=False
        )
        == "0x"
    )


def test_get_contract_code_empty_without_url_or_address():
    assert l1_rpc.get_contract_code("", "0x" + "11" * 20) == "0x"
    assert l1_rpc.get_contract_code("https://rpc.example.com", "") == "0x"
