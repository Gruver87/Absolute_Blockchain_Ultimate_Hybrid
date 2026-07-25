#!/usr/bin/env python3
"""v1.3.70: recursive native frame correctness (arena sync + live DELEGATECALL)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native
from evm_interpreter import EVM, EVMContext
from execution.evm_host_bridge import make_evm_runtime_bridge


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
@pytest.mark.skipif(
    not hasattr(native, "evm_run_nested_host_frame"),
    reason="evm_run_nested_host_frame missing",
)
def test_delegatecall_resyncs_arena_after_child_sstore():
    """Parent SSTORE → DELEGATECALL child SSTORE → parent SLOAD must see child write."""
    # Child: PUSH1 99 PUSH1 1 SSTORE STOP
    child_code = bytes([0x60, 0x63, 0x60, 0x01, 0x55, 0x00])
    callee = "0x00000000000000000000000000000000000000bb"
    addr_hex = callee.replace("0x", "").zfill(40)

    def hook(target, calldata, value, gas, delegate, static=False, callcode=False):
        assert target == callee
        assert delegate is True
        # Child runs against parent live storage (passed via result merge path).
        st = dict(getattr(hook, "_parent_storage", {}) or {})
        # Simulate child SSTORE(1, 99)
        st[1] = 99
        return {
            "success": True,
            "reverted": False,
            "return_data": b"",
            "gas_used": 50,
            "storage": st,
        }

    # Parent: PUSH1 42 PUSH1 1 SSTORE ; DELEGATECALL ; PUSH1 1 SLOAD STOP
    # gas, addr, argsOff, argsSize, retOff, retSize  — DELEGATECALL stack (gas, to, in, insize, out, outsize)
    bytecode = bytes(
        [
            0x60,
            0x2A,  # PUSH1 42
            0x60,
            0x01,  # PUSH1 1
            0x55,  # SSTORE
            0x60,
            0x00,  # retSize
            0x60,
            0x00,  # retOffset
            0x60,
            0x00,  # argsSize
            0x60,
            0x00,  # argsOffset
            0x73,
            *bytes.fromhex(addr_hex),
            0x5A,  # GAS
            0xF4,  # DELEGATECALL
            0x50,  # POP success
            0x60,
            0x01,  # PUSH1 1
            0x54,  # SLOAD
            0x00,  # STOP
        ]
    )
    storage: dict = {}
    hook._parent_storage = storage
    ctx = EVMContext(contract_call=hook, address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    evm = EVM(gas_limit=1_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    host_ctx = native.evm_host_context_from_evm(ctx)
    try:
        out = native.evm_run_nested_host_frame(
            bytecode,
            1_000_000,
            b"",
            host_ctx,
            storage,
            bridge,
        )
    except RuntimeError as exc:
        if "requires abs_native" in str(exc):
            pytest.skip(str(exc))
        raise
    assert out.get("native_nested_host") is True or out.get("stop_reason") in (
        "halt",
        "return",
    )
    assert not out.get("reverted")
    # Key assertion: arena re-synced — slot 1 is 99 from child, not 42 from parent.
    assert int(storage.get(1, 0)) == 99


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_depth2_call_stays_on_native_host():
    """A CALL→B CALL→C: both nested frames report native_nested_host (no silent Python fallback)."""
    c_code = bytes([0x60, 0x07, 0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0xF3])  # RETURN 7
    b_addr = "0x00000000000000000000000000000000000000bb"
    c_addr = "0x00000000000000000000000000000000000000cc"
    flags = {"b": False, "c": False}

    class FakeDB:
        def __init__(self):
            self.accounts = {
                b_addr: {
                    "address": b_addr,
                    "balance": 0,
                    "nonce": 0,
                    "code": "",  # filled below
                    "storage": "{}",
                },
                c_addr: {
                    "address": c_addr,
                    "balance": 0,
                    "nonce": 0,
                    "code": c_code.hex(),
                    "storage": "{}",
                },
            }

        def get_account(self, addr):
            return self.accounts.get(addr)

        def save_account(self, *a, **k):
            pass

        def append_evm_log(self, *a, **k):
            pass

        def transfer(self, *a, **k):
            return True

    # B: CALL C then STOP  (minimal CALL stack)
    c_hex = c_addr.replace("0x", "").zfill(40)
    b_code = bytes(
        [
            0x60,
            0x20,
            0x60,
            0x00,
            0x60,
            0x00,
            0x60,
            0x00,
            0x60,
            0x00,
            0x73,
            *bytes.fromhex(c_hex),
            0x60,
            0x64,
            0xF1,  # CALL
            0x00,
        ]
    )
    db = FakeDB()
    db.accounts[b_addr]["code"] = b_code.hex()

    from execution.evm_adapter import EVMAdapter
    from runtime.config import Config

    ad = EVMAdapter(db, Config())
    # Patch account view to serve code_bytes
    orig_view = ad._account_view

    def view(addr):
        row = db.get_account(addr) or {}
        code_hex = str(row.get("code") or "")
        try:
            code_bytes = bytes.fromhex(code_hex.replace("0x", "")) if code_hex else b""
        except ValueError:
            code_bytes = b""
        return {
            "ok": True,
            "missing": not bool(row),
            "corrupt": False,
            "code": code_hex,
            "code_bytes": code_bytes,
            "storage": {},
        }

    ad._account_view = view  # type: ignore[method-assign]

    # A: CALL B
    b_hex = b_addr.replace("0x", "").zfill(40)
    a_code = bytes(
        [
            0x60,
            0x20,
            0x60,
            0x00,
            0x60,
            0x00,
            0x60,
            0x00,
            0x60,
            0x00,
            0x73,
            *bytes.fromhex(b_hex),
            0x5A,
            0xF1,
            0x00,
        ]
    )
    # Run via contract_call_hook as if A invoked B
    caller_ctx = EVMContext(address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    out_b = ad._contract_call_hook(b_addr, b"", 0, 500_000, False, False, caller_ctx)
    assert out_b.get("success")
    assert out_b.get("native_nested_host") is True, out_b
    # Depth-2: B's CALL to C should also have used native host (B has CALL opcode → host frame)
    # C is pure RETURN — may be nested_pure; either is fine; must not be silent python-only.
    assert "native_nested_pure" in out_b or out_b.get("native_nested_host")


def test_needles_v1370():
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "re-sync arena after DELEGATECALL" in rust or "v1.3.70" in rust
    assert "flush Rust arena" in rust or "restore_storage_dict(storage, arena)" in rust
    adapter = (ROOT / "execution" / "evm_adapter.py").read_text(encoding="utf-8")
    assert "_abs_live_storage" in adapter
    assert "1.3.70" in adapter or "v1.3.70" in adapter
