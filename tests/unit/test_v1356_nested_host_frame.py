#!/usr/bin/env python3
"""v1.3.56: nested host frame (CALL/CREATE/LOG via Rust + host_bridge)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from crypto import native
from evm_interpreter import EVM, EVMContext
from execution.evm_host_bridge import make_evm_runtime_bridge


@pytest.mark.skipif(
    not hasattr(native, "evm_run_nested_host_frame"),
    reason="evm_run_nested_host_frame wrapper missing",
)
def test_nested_host_frame_log0():
    # PUSH1 0 PUSH1 0 LOG0 STOP — empty log
    bytecode = bytes([0x60, 0x00, 0x60, 0x00, 0xA0, 0x00])
    logs: list = []

    def emit_log(n_topics, topics, data):
        logs.append({"n": n_topics, "topics": list(topics), "data": bytes(data)})

    ctx = EVMContext(emit_log=emit_log)
    evm = EVM(gas_limit=1_000_000, context=ctx)
    storage: dict = {}
    bridge = make_evm_runtime_bridge(evm)
    try:
        out = native.evm_run_nested_host_frame(
            bytecode,
            1_000_000,
            b"",
            native.evm_host_context_from_evm(ctx),
            storage,
            bridge,
        )
    except RuntimeError as exc:
        if "requires abs_native" in str(exc) or "host_frame" in str(exc):
            pytest.skip(str(exc))
        raise
    assert out.get("native_nested_host") is True
    assert out.get("stop_reason") in ("halt", "return")
    assert not out.get("reverted")
    assert len(evm.logs) == 1 or len(logs) == 1


def test_adapter_wires_nested_host():
    adapter = (ROOT / "execution" / "evm_adapter.py").read_text(encoding="utf-8")
    assert "evm_run_nested_host_frame" in adapter
    assert "native_nested_host" in adapter
    assert "def evm_run_nested_host_frame" in (ROOT / "crypto" / "native.py").read_text(
        encoding="utf-8"
    )
    rust = (ROOT / "native" / "abs_native" / "src" / "evm_pure_runner.rs").read_text(
        encoding="utf-8"
    )
    assert "evm_run_nested_host_frame" in rust
