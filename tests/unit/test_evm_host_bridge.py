#!/usr/bin/env python3
"""Python host bridge adapter for native EVM runner."""

from evm_interpreter import EVM, EVMContext
from execution.evm_host_bridge import EvmHostBridge, EvmRuntimeBridge, make_evm_runtime_bridge


def test_host_bridge_balance():
    ctx = EVMContext(balance_of=lambda addr: 999 if addr.endswith("abc") else 0)
    bridge = EvmHostBridge(ctx)
    assert bridge.balance("0x000000000000000000000000000000000000abc") == 999


def test_runtime_bridge_selfdestruct_stops():
    destroyed = []

    def _selfdestruct(addr: str) -> None:
        destroyed.append(addr)

    ctx = EVMContext(selfdestruct=_selfdestruct)
    evm = EVM(context=ctx)
    bridge = EvmRuntimeBridge(evm)
    out = bridge.apply_host_op(
        0xFF,
        [0x1234],
        bytearray(),
        evm.gas_limit,
        evm.gas_used,
        evm.storage,
        evm.return_data,
    )
    assert out["running"] is False
    assert len(destroyed) == 1


def test_runtime_bridge_log_via_native_segment():
    logs = []

    def _emit_log(n_topics: int, topics, data: bytes) -> None:
        logs.append((n_topics, list(topics), bytes(data)))

    ctx = EVMContext(emit_log=_emit_log)
    evm = EVM(context=ctx)
    # LOG1: offset=0, size=1, topic=0x2a
    bytecode = bytes([0x60, 0x00, 0x60, 0x01, 0x60, 0x2A, 0xA1, 0x00])
    result = evm.execute_bytecode(bytecode)
    assert result["reverted"] is False
    assert logs
    assert logs[0][0] == 1


def test_make_runtime_bridge():
    evm = EVM()
    assert isinstance(make_evm_runtime_bridge(evm), EvmRuntimeBridge)
