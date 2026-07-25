#!/usr/bin/env python3
"""v1.3.82: inline CREATE with eligible RETURN init (runtime from return_data)."""

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


DEPLOYER = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# Init: mem[0]=STOP; RETURN 1 byte → deployed runtime = 0x00
# 60 00 60 00 53 60 01 60 00 F3
RETURN_STOP_INIT = bytes.fromhex("600060005360016000f3")


def _create_with_init_in_memory(init: bytes, value: int = 0) -> bytes:
    """Write init bytes via MSTORE8 loop, then CREATE."""
    out = bytearray()
    for i, b in enumerate(init):
        out.extend([0x60, b & 0xFF, 0x60, i & 0xFF, 0x53])  # PUSH byte, PUSH offset, MSTORE8
    out.extend(
        [
            0x60,
            value & 0xFF,
            0x60,
            0x00,  # offset
            0x60,
            len(init) & 0xFF,  # size
            0xF0,  # CREATE
            0x00,
        ]
    )
    return bytes(out)


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_inline_create_return_runtime_stop():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    bytecode = _create_with_init_in_memory(RETURN_STOP_INIT)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=5)
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
    assert int(bs.get("native_inline_create_runtime_len") or 0) == 1
    addr = bs["native_inline_create_address"]
    expected = native.evm_deploy_address_create(DEPLOYER, 5, len(RETURN_STOP_INIT))
    assert addr.lower() == expected.lower()
    code = bs["codes"][addr]
    assert bytes(code) == b"\x00"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_inline_create_return_runtime_with_value():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    bytecode = _create_with_init_in_memory(RETURN_STOP_INIT, value=4)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=2)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {},
        "storages": {},
        "balances": {DEPLOYER: 20},
    }
    evm = EVM(gas_limit=2_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    out = native.evm_run_nested_host_frame(
        bytecode, 2_000_000, b"", host_ctx, storage, bridge
    )
    assert not out.get("reverted"), out
    assert hook_calls["n"] == 0
    addr = host_ctx["bridge_state"]["native_inline_create_address"]
    bal = host_ctx["bridge_state"]["balances"]
    assert int(bal[DEPLOYER]) == 16
    assert int(bal[addr]) == 4
    assert bytes(host_ctx["bridge_state"]["codes"][addr]) == b"\x00"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_inline_create2_return_runtime():
    hook_calls = {"n": 0}

    def create_hook(*a, **k):
        hook_calls["n"] += 1
        return {"success": False, "reverted": True, "gas_used": 0}

    init = RETURN_STOP_INIT
    out = bytearray()
    for i, b in enumerate(init):
        out.extend([0x60, b & 0xFF, 0x60, i & 0xFF, 0x53])
    out.extend(
        [
            0x60,
            0x00,  # value
            0x60,
            0x00,  # offset
            0x60,
            len(init) & 0xFF,
            0x60,
            0x09,  # salt
            0xF5,
            0x00,
        ]
    )
    bytecode = bytes(out)
    storage: dict = {}
    ctx = EVMContext(contract_create=create_hook, address=DEPLOYER, block_number=1)
    host_ctx = native.evm_host_context_from_evm(ctx)
    host_ctx["bridge_state"] = {
        "codes": {},
        "storages": {},
        "create2_eip1014": True,
    }
    evm = EVM(gas_limit=2_000_000, context=ctx)
    evm.storage = storage
    bridge = make_evm_runtime_bridge(evm)
    result = native.evm_run_nested_host_frame(
        bytecode, 2_000_000, b"", host_ctx, storage, bridge
    )
    assert not result.get("reverted"), result
    assert hook_calls["n"] == 0
    bs = host_ctx["bridge_state"]
    assert bs.get("native_inline_create2") is True
    assert bs.get("native_inline_create_runtime") is True
    addr = bs["native_inline_create_address"]
    expected = native.evm_create2_address_eip1014(DEPLOYER, 9, init)
    assert addr.lower() == expected.lower()
    assert bytes(bs["codes"][addr]) == b"\x00"


def test_needles_v1382():
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "run_inline_create_init" in rust
    assert "native_inline_create_runtime" in rust
    assert "MAX_INLINE_CREATE_CODE_BYTES" in rust
    assert "v1.3.82" in rust
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "1.3.82-industrial" in cfg
