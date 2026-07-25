#!/usr/bin/env python3
"""v1.3.85: P2P per-peer outbound egress bandwidth (cost-weighted)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import abs_native

from crypto import native
from network.p2p_node import P2PNode, RATE_LIMIT_EXEMPT_TYPES
from runtime.config import Config


def test_needles_v1385():
    rl = (ROOT / "native" / "abs_native" / "src" / "p2p_rate_limit.rs").read_text(
        encoding="utf-8"
    )
    assert "egress_byte_limit" in rl
    assert "admit_egress" in rl
    assert "egress_bandwidth_exceeded" in rl
    assert "p2p_egress_admit" in rl
    assert "v1.3.85" in rl
    notes = (ROOT / "RELEASE_NOTES_v1.3.85.md").read_text(encoding="utf-8")
    assert "1.3.85-industrial" in notes
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_egress_rejects_total" in metrics
    node = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_egress_ok" in node
    assert "admit_egress" in node
    assert hasattr(abs_native, "p2p_egress_admit")
    assert hasattr(native, "p2p_egress_admit")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_egress_cost_units_match_ingress():
    assert native.p2p_egress_cost_units("ping", 100) == native.p2p_ingress_cost_units(
        "ping", 100
    )
    assert native.p2p_egress_cost_units("blocks", 100) == 200


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_egress_budget_rejects_independently_of_ingress():
    now = time.time()
    # inbound unlimited (byte_limit=0), outbound tiny
    table = native.P2PRateLimitTable(
        500, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 500, 0, 50
    )
    a1 = native.p2p_egress_admit("p1", 40, now, "attestation", table)
    assert a1["ok"] is True
    a2 = native.p2p_egress_admit("p1", 40, now, "attestation", table)
    assert a2["ok"] is False
    assert a2["reason"] == "egress_bandwidth_exceeded"
    assert int(table.egress_rejects) >= 1
    # inbound still free
    assert table.admit_bandwidth("p1", 10_000, now, "attestation") is None


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_blocks_egress_cost_burns_faster():
    now = time.time()
    cost = native.p2p_egress_cost_units("blocks", 40)
    assert cost == 80
    table = native.P2PRateLimitTable(
        500, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 500, 0, cost - 1
    )
    out = native.p2p_egress_admit("p1", 40, now, "blocks", table)
    assert out["ok"] is False and out["reason"] == "egress_bandwidth_exceeded"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_exposes_egress_status():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._rl_table is not None
    assert int(node._rl_table.egress_byte_limit) == int(cfg.p2p_max_outbound_bytes_per_sec)
    status = node.get_p2p_security_status()
    assert status["native_p2p_egress"] is True
    assert status["max_outbound_bytes_per_sec"] == cfg.p2p_max_outbound_bytes_per_sec
    assert "egress_rejects" in status
