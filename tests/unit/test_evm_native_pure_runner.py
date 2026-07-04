#!/usr/bin/env python3
"""Rust-backed EVM pure-opcode segment runner."""

import pytest

from crypto import native
from evm_interpreter import EVM, EVMContext


def test_opcode_is_host_and_bridge():
    assert native.evm_opcode_is_host(0xF1) is True
    assert native.evm_opcode_is_host(0x01) is False
    assert native.evm_opcode_is_bridge(0x31) is True
    assert native.evm_opcode_is_bridge(0x33) is False
    assert native.evm_opcode_is_host(0x31) is False
    assert native.evm_opcode_is_host(0xA0) is True


def _host_ctx(**kwargs):
    base = {
        "address": 0,
        "caller": 0,
        "origin": 0,
        "value": 0,
        "timestamp": 0,
        "block_number": 0,
        "chain_id": 77777,
    }
    base.update(kwargs)
    return base


def test_pure_segment_runs_arithmetic_and_stops():
    # PUSH1 2, PUSH1 3, ADD, STOP
    bytecode = bytes([0x60, 0x02, 0x60, 0x03, 0x01, 0x00])
    table = native.evm_build_jumpdest_table(bytecode)
    stack = []
    memory = bytearray()
    seg = native.evm_run_pure_until_host(
        bytecode, 0, 1_000_000, 0, stack, memory, table, b"", b"", _host_ctx()
    )
    assert seg["stop_reason"] == "halt"
    assert seg["running"] is False
    assert seg["stack"] == [5]
    assert seg["gas_used"] > 0
    assert seg["steps"] == 4


def test_pure_segment_stops_at_bridge_without_host_bridge():
    # PUSH1 0, BALANCE — stops when no bridge object is passed
    bytecode = bytes([0x60, 0x00, 0x31])
    table = native.evm_build_jumpdest_table(bytecode)
    seg = native.evm_run_pure_until_host(
        bytecode, 0, 1_000_000, 0, [], bytearray(), table, b"", b"", _host_ctx()
    )
    assert seg["stop_reason"] == "host"
    assert seg["host_opcode"] == 0x31
    assert seg["pc"] == 2
    assert seg["stack"] == [0]
    assert seg["running"] is True


def test_pure_segment_runs_balance_via_host_bridge():
    class Bridge:
        def balance(self, addr: str) -> int:
            assert addr.startswith("0x")
            return 12345

    bytecode = bytes([0x60, 0x00, 0x31, 0x00])  # PUSH1 0, BALANCE, STOP
    table = native.evm_build_jumpdest_table(bytecode)
    seg = native.evm_run_pure_until_host(
        bytecode,
        0,
        1_000_000,
        0,
        [],
        bytearray(),
        table,
        b"",
        b"",
        _host_ctx(),
        None,
        Bridge(),
    )
    assert seg["stop_reason"] == "halt"
    assert seg["stack"] == [12345]


def test_pure_segment_runs_caller_and_chainid():
    caller = int("ab" * 20, 16)
    bytecode = bytes([0x33, 0x46, 0x00])  # CALLER, CHAINID, STOP
    table = native.evm_build_jumpdest_table(bytecode)
    seg = native.evm_run_pure_until_host(
        bytecode,
        0,
        1_000_000,
        0,
        [],
        bytearray(),
        table,
        b"",
        b"",
        _host_ctx(caller=caller, chain_id=42),
    )
    assert seg["stop_reason"] == "halt"
    assert seg["stack"] == [caller, 42]


def test_pure_segment_sload_sstore():
    storage = {1: 42}
    bytecode = bytes([
        0x60, 0x2A,  # PUSH1 42
        0x60, 0x02,  # PUSH1 2
        0x55,        # SSTORE
        0x60, 0x02,  # PUSH1 2
        0x54,        # SLOAD
        0x00,        # STOP
    ])
    table = native.evm_build_jumpdest_table(bytecode)
    seg = native.evm_run_pure_until_host(
        bytecode,
        0,
        10_000_000,
        0,
        [],
        bytearray(),
        table,
        b"",
        b"",
        _host_ctx(),
        storage,
    )
    assert seg["stop_reason"] == "halt"
    assert seg["stack"] == [42]
    assert storage[2] == 42


def test_interpreter_uses_native_segment_for_pure_bytecode():
    bytecode = bytes([0x60, 0x02, 0x60, 0x03, 0x01, 0x00])
    result = EVM().execute_bytecode(bytecode)
    assert result["reverted"] is False
    assert result["stack"] == [5]


def test_pure_segment_stops_at_interpreter_host_without_runtime_bridge():
    # CALL without runtime bridge stops segment
    bytecode = bytes([0x60, 0x00] * 7 + [0xF1])  # zeros + CALL
    table = native.evm_build_jumpdest_table(bytecode)
    seg = native.evm_run_pure_until_host(
        bytecode,
        0,
        10_000_000,
        0,
        [0] * 7,
        bytearray(),
        table,
        b"",
        b"",
        _host_ctx(),
    )
    assert seg["stop_reason"] == "host"
    assert seg["host_opcode"] == 0xF1


def test_interpreter_still_handles_caller_after_native_segment():
    ctx_caller = "0x" + "ab" * 20
    ctx = EVMContext(caller=ctx_caller)
    bytecode = bytes([0x33, 0x00])  # CALLER, STOP
    result = EVM(context=ctx).execute_bytecode(bytecode)
    assert result["reverted"] is False
    assert result["stack"] == [int(ctx_caller.replace("0x", ""), 16)]


@pytest.mark.skipif(not native.native_available(), reason="abs_native required")
def test_native_required_for_pure_runner():
    assert hasattr(native, "evm_run_pure_until_host")
    assert hasattr(native, "evm_run_until_halt")


def test_native_run_until_halt_completes():
    bytecode = bytes([0x60, 0x02, 0x60, 0x03, 0x01, 0x00])
    table = native.evm_build_jumpdest_table(bytecode)
    seg = native.evm_run_until_halt(
        bytecode, 0, 1_000_000, 0, [], bytearray(), table, b"", b"", _host_ctx()
    )
    assert seg["stop_reason"] == "halt"
    assert seg["stack"] == [5]
    assert seg["steps"] == 4


def test_interpreter_prefers_native_until_halt():
    bytecode = bytes([0x60, 0x02, 0x60, 0x03, 0x01, 0x00])
    result = EVM().execute_bytecode(bytecode)
    assert result["reverted"] is False
    assert result["stack"] == [5]
