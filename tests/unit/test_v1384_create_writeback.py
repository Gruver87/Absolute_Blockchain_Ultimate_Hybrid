#!/usr/bin/env python3
"""v1.3.84: inline CREATE/CREATE2 → save_account pending writeback journal."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native
from evm_interpreter import EVM, EVMContext
from execution.evm_adapter import EVMAdapter
from execution.evm_host_bridge import make_evm_runtime_bridge
from runtime.config import Config


DEPLOYER = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
# Init: mem[0]=STOP; RETURN 1 byte → runtime 0x00
RETURN_STOP_INIT = bytes.fromhex("600060005360016000f3")


def _create_with_init_in_memory(init: bytes, value: int = 0) -> bytes:
    out = bytearray()
    for i, b in enumerate(init):
        out.extend([0x60, b & 0xFF, 0x60, i & 0xFF, 0x53])
    out.extend(
        [
            0x60,
            value & 0xFF,
            0x60,
            0x00,
            0x60,
            len(init) & 0xFF,
            0xF0,
            0x00,
        ]
    )
    return bytes(out)


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_empty_create_enqueues_save_account():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    bytecode = bytes([0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0xF0, 0x00])
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=3)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {"codes": {}, "storages": {}, "balances": {DEPLOYER: 0}}
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 1_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted"), out
    assert hook_calls["n"] == 0
    bs = host_ctx["bridge_state"]
    assert bs.get("native_inline_writeback_create") is True
    ops = [dict(o) for o in (bs.get("pending_writeback_ops") or [])]
    assert len(ops) == 1
    assert ops[0]["op"] == "save_account"
    assert ops[0]["address"].lower() == bs["native_inline_create_address"].lower()
    assert ops[0]["code"] == ""
    assert int(ops[0]["balance"]) == 0
    assert ops[0]["storage"] == "{}"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_create_runtime_save_account_code_hex():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    bytecode = _create_with_init_in_memory(RETURN_STOP_INIT)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=7)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {"codes": {}, "storages": {}}
    evm = EVM(gas_limit=2_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 2_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted"), out
    assert hook_calls["n"] == 0
    bs = host_ctx["bridge_state"]
    assert bs.get("native_inline_create_runtime") is True
    ops = [dict(o) for o in (bs.get("pending_writeback_ops") or [])]
    assert len(ops) == 1
    assert ops[0]["op"] == "save_account"
    assert ops[0]["code"] == "00"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_adapter_flushes_save_account_into_journal():
    class MemDB:
        def get_account(self, addr):
            return None

        def get_chain_tip(self):
            return 0

    ad = EVMAdapter(MemDB(), Config())
    ad.begin_writeback_journal()
    host_ctx = {
        "bridge_state": {
            "pending_writeback_ops": [
                {
                    "op": "save_account",
                    "address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                    "balance": 0,
                    "nonce": 0,
                    "code": "00",
                    "storage": "{}",
                    "native_inline_writeback": True,
                }
            ]
        }
    }
    ops = ad._take_bridge_pending_writeback(host_ctx)
    ad._apply_nested_writeback_ops(ops)
    assert len(ad._writeback_journal) == 1
    assert ad._writeback_journal[0]["op"] == "save_account"
    assert ad._writeback_journal[0]["code"] == "00"


def test_needles_v1384():
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "push_pending_writeback_save_account" in rust
    assert "native_inline_writeback_create" in rust
    assert "v1.3.84" in rust
    notes = (ROOT / "RELEASE_NOTES_v1.3.84.md").read_text(encoding="utf-8")
    assert "1.3.84-industrial" in notes
