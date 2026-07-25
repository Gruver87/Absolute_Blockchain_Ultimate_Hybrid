#!/usr/bin/env python3
"""v1.3.78: P2P per-peer bandwidth / cost-weighted ingress budget."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import abs_native

from crypto import native
from network.p2p_node import P2PNode, RATE_LIMIT_EXEMPT_TYPES
from runtime.config import Config


def test_needles_v1378():
    rl = (ROOT / "native" / "abs_native" / "src" / "p2p_rate_limit.rs").read_text(
        encoding="utf-8"
    )
    assert "byte_limit" in rl
    assert "bandwidth_exceeded" in rl
    assert "ingress_cost_units" in rl
    assert "p2p_ingress_cost_units" in rl
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "1.3.78-industrial" in cfg
    assert "p2p_max_bytes_per_sec" in cfg
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_bandwidth_rejects_total" in metrics
    assert hasattr(abs_native, "p2p_ingress_cost_units")
    assert hasattr(native, "p2p_ingress_cost_units")


def test_cost_units_weight_blocks():
    assert native.p2p_ingress_cost_units("ping", 100) == 100
    assert native.p2p_ingress_cost_units("blocks", 100) == 200
    assert native.p2p_ingress_cost_units("block", 50) == 100


def test_bandwidth_budget_rejects():
    # High message limits; tiny byte budget (cost = nbytes for attestation).
    now = time.time()
    payload = {"type": "attestation", "data": {"pad": "x" * 20}}
    line = (json.dumps(payload) + "\n").encode()
    nbytes = len(line)
    table = native.P2PRateLimitTable(
        500, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 500, nbytes + 10
    )
    a1 = native.p2p_ingress_admit(line, "p1", now, 2**20, None, table)
    assert a1["ok"] is True
    a2 = native.p2p_ingress_admit(line, "p1", now, 2**20, None, table)
    assert a2["ok"] is False
    assert a2["reason"] == "bandwidth_exceeded"
    assert int(table.bandwidth_rejects) >= 1


def test_blocks_cost_burns_faster():
    now = time.time()
    line = (json.dumps({"type": "blocks", "data": {"n": "y" * 40}}) + "\n").encode()
    cost = native.p2p_ingress_cost_units("blocks", len(line))
    assert cost == len(line) * 2
    # Budget just under one weighted message
    table = native.P2PRateLimitTable(
        500, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 500, cost - 1
    )
    out = native.p2p_ingress_admit(line, "p1", now, 2**20, None, table)
    assert out["ok"] is False and out["reason"] == "bandwidth_exceeded"

def test_p2p_node_exposes_bandwidth_status():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._rl_table is not None
    assert int(node._rl_table.byte_limit) == int(cfg.p2p_max_bytes_per_sec)
    status = node.get_p2p_security_status()
    assert "max_bytes_per_sec" in status
    assert status["max_bytes_per_sec"] == cfg.p2p_max_bytes_per_sec
