#!/usr/bin/env python3
"""v1.3.87: unified native P2P egress prepare (encode + allowlist + size + egress)."""

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
from network.p2p_node import ALLOWED_WIRE_TYPES, P2PNode, RATE_LIMIT_EXEMPT_TYPES
from runtime.config import Config


def test_needles_v1387():
    ingress = (ROOT / "native" / "abs_native" / "src" / "p2p_ingress.rs").read_text(
        encoding="utf-8"
    )
    assert "p2p_egress_prepare" in ingress
    assert "v1.3.87" in ingress
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_prepare_outbound" in p2p
    assert "p2p_egress_prepare" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "1.3.87-industrial" in cfg
    assert hasattr(abs_native, "p2p_egress_prepare")
    assert hasattr(native, "p2p_egress_prepare")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_egress_prepare_ok_roundtrip():
    table = native.P2PRateLimitTable(
        500, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 500, 0, 0
    )
    out = native.p2p_egress_prepare(
        "ping",
        "null",
        "p1",
        time.time(),
        2 * 1024 * 1024,
        list(ALLOWED_WIRE_TYPES),
        table,
    )
    assert out["ok"] is True
    payload = bytes(out["payload"])
    assert payload.endswith(b"\n")
    assert b"ping" in payload
    parsed = native.parse_p2p_wire_line(payload)
    assert parsed["type"] == "ping"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_egress_prepare_rejects_disallowed_type():
    table = native.P2PRateLimitTable(
        500, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 500, 0, 0
    )
    out = native.p2p_egress_prepare(
        "not_a_real_type",
        "{}",
        "p1",
        time.time(),
        2 * 1024 * 1024,
        list(ALLOWED_WIRE_TYPES),
        table,
    )
    assert out["ok"] is False
    assert "p2p_type_not_allowed" in str(out.get("reason") or "")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_egress_prepare_bandwidth_reject():
    now = time.time()
    # Probe wire size with a generous egress budget, then pin limit to one message.
    probe_table = native.P2PRateLimitTable(
        500, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 500, 0, 10_000_000
    )
    probe = native.p2p_egress_prepare(
        "attestation",
        "{}",
        "probe",
        now,
        2**20,
        list(ALLOWED_WIRE_TYPES),
        probe_table,
    )
    assert probe["ok"] is True
    nbytes = int(probe["nbytes"])
    cost = int(native.p2p_egress_cost_units("attestation", nbytes))
    assert cost > 0
    table = native.P2PRateLimitTable(
        500, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 500, 0, cost
    )
    a1 = native.p2p_egress_prepare(
        "attestation", "{}", "p1", now, 2**20, list(ALLOWED_WIRE_TYPES), table
    )
    assert a1["ok"] is True
    a2 = native.p2p_egress_prepare(
        "attestation", "{}", "p1", now, 2**20, list(ALLOWED_WIRE_TYPES), table
    )
    assert a2["ok"] is False
    assert a2["reason"] == "egress_bandwidth_exceeded"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_exposes_egress_prepare_status():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    node = P2PNode(cfg, MagicMock(), MagicMock())
    status = node.get_p2p_security_status()
    assert status.get("native_p2p_egress_prepare") is True
