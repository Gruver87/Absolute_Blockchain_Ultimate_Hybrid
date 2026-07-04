#!/usr/bin/env python3
"""Python host bridge adapter for native EVM runner."""

from evm_interpreter import EVMContext
from execution.evm_host_bridge import EvmHostBridge, make_evm_host_bridge


def test_host_bridge_balance():
    ctx = EVMContext(balance_of=lambda addr: 999 if addr.endswith("abc") else 0)
    bridge = EvmHostBridge(ctx)
    assert bridge.balance("0x000000000000000000000000000000000000abc") == 999


def test_make_host_bridge_returns_adapter():
    ctx = EVMContext()
    assert isinstance(make_evm_host_bridge(ctx), EvmHostBridge)
