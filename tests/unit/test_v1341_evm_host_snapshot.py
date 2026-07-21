#!/usr/bin/env python3
"""v1.3.41: EVM host storage snapshot around runner."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native
from evm_interpreter import EVM, EVMContext


def test_native_host_snapshot_symbols():
    assert native.native_available()
    assert hasattr(native, "evm_host_snapshot_storage")
    assert hasattr(native, "evm_host_restore_storage")


def test_snapshot_restore_roundtrip():
    storage = {1: 7, 2: 9}
    snap = native.evm_host_snapshot_storage(storage)
    storage[1] = 99
    storage[3] = 1
    native.evm_host_restore_storage(storage, snap)
    assert storage.get(1) == 7
    assert storage.get(2) == 9
    assert 3 not in storage


def test_sstore_then_revert_clears_dirty_storage():
    # PUSH1 7 PUSH1 0 SSTORE PUSH1 0 PUSH1 0 REVERT
    bytecode = bytes.fromhex("600760005560006000fd")
    evm = EVM(gas_limit=1_000_000, context=EVMContext())
    evm.storage = {5: 42}
    out = evm.execute_bytecode(bytecode)
    assert out["reverted"] is True
    assert out["storage"].get(5) == 42
    assert 0 not in out["storage"]


def test_sstore_commit_keeps_storage():
    # PUSH1 7 PUSH1 0 SSTORE STOP
    bytecode = bytes.fromhex("600760005500")
    evm = EVM(gas_limit=1_000_000, context=EVMContext())
    out = evm.execute_bytecode(bytecode)
    assert out["reverted"] is False
    assert out["storage"].get(0) == 7


def test_wiring():
    text = Path("evm_interpreter.py").read_text(encoding="utf-8")
    assert "_take_host_storage_snap" in text
    assert "evm_host_snapshot_storage" in text
    adapter = Path("execution/evm_adapter.py").read_text(encoding="utf-8")
    assert 'if not result.get("reverted"):' in adapter
    assert "def evm_host_snapshot_storage" in Path("crypto/native.py").read_text(encoding="utf-8")
