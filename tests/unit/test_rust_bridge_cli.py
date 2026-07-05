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


def _synthetic_bridge_env():
    env = {**os.environ, "BRIDGE_ALLOW_SYNTHETIC": "1"}
    for key in ("ETH_RPC_URL", "BSC_RPC_URL", "POLYGON_RPC_URL", "BRIDGE_REQUIRE_L1_PROOF"):
        env.pop(key, None)
    return env


def test_rust_bridge_cli_returns_tx_hash():
    exe = _bridge_bin()
    payload = json.dumps({"command": "bridge", "args": {"amount": 10}}).encode()
    env = _synthetic_bridge_env()
    proc = subprocess.run([exe], input=payload, capture_output=True, timeout=10, env=env)
    assert proc.returncode == 0, proc.stderr.decode()
    out = json.loads(proc.stdout.decode())
    assert out["tx_hash"].startswith("0x")
    assert len(out["tx_hash"]) == 66


def test_rust_bridge_cli_rejects_synthetic_without_dev_flag():
    exe = _bridge_bin()
    payload = json.dumps({"command": "bridge", "args": {"amount": 10}}).encode()
    env = os.environ.copy()
    env.pop("BRIDGE_ALLOW_SYNTHETIC", None)
    proc = subprocess.run([exe], input=payload, capture_output=True, timeout=10, env=env)
    if proc.returncode == 0:
        pytest.skip("rebuild bridge/abs_bridge_bin for production synthetic gate")
    out = json.loads(proc.stdout.decode())
    assert out["status"] == "error"
    assert "l1_tx_hash" in (out.get("error") or "")


def test_rust_bridge_cli_incoming_command():
    exe = _bridge_bin()
    payload = json.dumps({
        "command": "incoming",
        "args": {"tx_hash": "0xabc", "recipient": "0x1", "amount": 5, "from_chain": "ethereum"},
    }).encode()
    env = _synthetic_bridge_env()
    proc = subprocess.run([exe], input=payload, capture_output=True, timeout=10, env=env)
    assert proc.returncode == 0, proc.stderr.decode()
    out = json.loads(proc.stdout.decode())
    assert out["status"] == "ok"
    assert out["tx_hash"].startswith("0x")
    if "source" in out:
        assert "abs_bridge_bin" in out["source"]
    if "proof_id" in out:
        assert out["proof_id"].startswith("prf_")
