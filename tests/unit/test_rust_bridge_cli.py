#!/usr/bin/env python3
"""Rust bridge CLI subprocess integration."""
import json
import os
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
BIN = os.path.join(ROOT, "bridge", "abs_bridge_bin")
BIN_EXE = BIN + ".exe"


def _bridge_bin():
    if os.path.isfile(BIN_EXE):
        return BIN_EXE
    if os.path.isfile(BIN):
        return BIN
    pytest.skip("bridge/abs_bridge_bin not built — run scripts/build_bridge.sh")


def test_rust_bridge_cli_returns_tx_hash():
    exe = _bridge_bin()
    payload = json.dumps({"command": "bridge", "args": {"amount": 10}}).encode()
    proc = subprocess.run([exe], input=payload, capture_output=True, timeout=10)
    assert proc.returncode == 0, proc.stderr.decode()
    out = json.loads(proc.stdout.decode())
    assert out["tx_hash"].startswith("0x")
    assert len(out["tx_hash"]) == 66


def test_rust_bridge_cli_incoming_command():
    exe = _bridge_bin()
    payload = json.dumps({
        "command": "incoming",
        "args": {"tx_hash": "0xabc", "recipient": "0x1", "amount": 5, "from_chain": "ethereum"},
    }).encode()
    proc = subprocess.run([exe], input=payload, capture_output=True, timeout=10)
    assert proc.returncode == 0, proc.stderr.decode()
    out = json.loads(proc.stdout.decode())
    assert out["status"] == "ok"
    assert out["tx_hash"].startswith("0x")
