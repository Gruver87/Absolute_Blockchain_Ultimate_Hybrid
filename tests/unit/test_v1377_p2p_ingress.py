#!/usr/bin/env python3
"""v1.3.77: Rust P2P ingress admit (wire+rate) + connection governor."""

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
from network.p2p_node import MSG_NEW_TX, MSG_PING, P2PNode, RATE_LIMIT_EXEMPT_TYPES
from runtime.config import Config


def test_needles_v1377():
    ingress = (ROOT / "native" / "abs_native" / "src" / "p2p_ingress.rs").read_text(
        encoding="utf-8"
    )
    assert "p2p_ingress_admit" in ingress
    assert "P2PConnectionGovernor" in ingress
    assert "v1.3.77" in ingress or "Unified P2P ingress" in ingress
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "p2p_ingress_admit" in p2p
    assert "_use_native_ingress" in p2p
    assert "P2PConnectionGovernor" in p2p
    assert "p2p_max_inbound_per_ip" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "1.3.77-industrial" in cfg
    assert "p2p_max_inbound_per_ip" in cfg
    assert hasattr(abs_native, "p2p_ingress_admit")
    assert hasattr(abs_native, "P2PConnectionGovernor")
    assert hasattr(native, "p2p_ingress_admit")


def test_ingress_admit_wire_and_rate():
    table = native.P2PRateLimitTable(2, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 0)
    now = time.time()
    line = (json.dumps({"type": "attestation", "data": {"x": 1}}) + "\n").encode()
    a1 = native.p2p_ingress_admit(line, "p1", now, 2 * 1024 * 1024, None, table)
    assert a1["ok"] is True and a1["type"] == "attestation"
    a2 = native.p2p_ingress_admit(line, "p1", now, 2 * 1024 * 1024, None, table)
    assert a2["ok"] is True
    a3 = native.p2p_ingress_admit(line, "p1", now, 2 * 1024 * 1024, None, table)
    assert a3["ok"] is False and a3["reason"] == "rate_limit_exceeded"


def test_ingress_admit_rejects_oversized():
    table = native.P2PRateLimitTable(500, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 0)
    huge = b'{"type":"ping","data":null}\n' + (b"x" * 10_000)
    out = native.p2p_ingress_admit(huge, "p1", time.time(), 4096, ["ping"], table)
    assert out["ok"] is False
    assert out["reason"] == "p2p_line_too_large"


def test_ingress_exempt_secondary_budget():
    table = native.P2PRateLimitTable(500, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 2)
    now = time.time()
    line = (json.dumps({"type": MSG_NEW_TX, "data": {}}) + "\n").encode()
    assert native.p2p_ingress_admit(line, "p1", now, 2**20, None, table)["ok"]
    assert native.p2p_ingress_admit(line, "p1", now, 2**20, None, table)["ok"]
    denied = native.p2p_ingress_admit(line, "p1", now, 2**20, None, table)
    assert denied["ok"] is False and denied["reason"] == "exempt_rate_exceeded"


def test_connection_governor_per_ip():
    gov = native.P2PConnectionGovernor(10, 2)
    assert gov.allow_inbound(0, "1.2.3.4") is None
    gov.on_connected("1.2.3.4")
    gov.on_connected("1.2.3.4")
    assert gov.inbound_ip_count("1.2.3.4") == 2
    assert gov.allow_inbound(2, "1.2.3.4") == "max_inbound_per_ip"
    gov.on_disconnected("1.2.3.4")
    assert gov.allow_inbound(2, "1.2.3.4") is None
    assert gov.allow_outbound(10) == "max_peers"


def test_p2p_node_enables_ingress():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._rl_table is not None
    assert node._use_native_ingress is True
    assert node._conn_governor is not None
    status = node.get_p2p_security_status()
    assert status.get("native_p2p_ingress") is True
    assert status.get("native_conn_governor") is True


def test_ping_exempt_still_allowed_under_primary():
    table = native.P2PRateLimitTable(1, 5, 300, sorted(RATE_LIMIT_EXEMPT_TYPES), 100)
    now = time.time()
    ping = (json.dumps({"type": MSG_PING, "data": None}) + "\n").encode()
    for _ in range(5):
        assert native.p2p_ingress_admit(ping, "p1", now, 2**20, None, table)["ok"]
