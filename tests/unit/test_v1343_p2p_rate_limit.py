#!/usr/bin/env python3
"""v1.3.43: native P2P rate-limit / strike table."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import abs_native

from crypto import native
from network.p2p_node import (
    MSG_NEW_BLOCK,
    MSG_PING,
    P2PNode,
    RATE_LIMIT_EXEMPT_TYPES,
)
from runtime.config import Config


def test_native_symbols():
    assert hasattr(abs_native, "P2PRateLimitTable")
    assert hasattr(abs_native, "p2p_rate_limit_tick")
    assert hasattr(abs_native, "p2p_strike_should_ban")
    assert hasattr(native, "P2PRateLimitTable")
    assert hasattr(native, "p2p_rate_limit_is_exempt")


def test_rate_limit_tick_and_exempt():
    ok, c, _s = native.p2p_rate_limit_tick(0, 0.0, 100.0, 3)
    assert ok and c == 1
    ok, c, _s = native.p2p_rate_limit_tick(c, 100.0, 100.1, 3)
    assert ok and c == 2
    ok, c, _s = native.p2p_rate_limit_tick(c, 100.0, 100.2, 3)
    assert ok and c == 3
    ok, c, _s = native.p2p_rate_limit_tick(c, 100.0, 100.3, 3)
    assert not ok and c == 4
    for t in RATE_LIMIT_EXEMPT_TYPES:
        assert native.p2p_rate_limit_is_exempt(t)


def test_table_rate_and_strike():
    table = native.P2PRateLimitTable(3, 2, 300, sorted(RATE_LIMIT_EXEMPT_TYPES))
    now = time.time()
    assert table.rate_ok("p1", MSG_PING, now) is True
    assert table.rate_ok("p1", "attestation", now) is True
    assert table.rate_ok("p1", "attestation", now) is True
    assert table.rate_ok("p1", "attestation", now) is True
    assert table.rate_ok("p1", "attestation", now) is False
    assert table.strike("p1", now) is False
    assert table.strike_count("p1") == 1
    assert table.strike("p1", now) is True
    assert table.is_banned("p1", now) is True
    assert native.p2p_strike_should_ban(2, 2) is True


def test_p2p_node_uses_native_table():
    cfg = Config()
    cfg.p2p_max_messages_per_sec = 3
    cfg.p2p_rate_limit_strikes = 2
    node = P2PNode(cfg, None, None)
    assert node._rl_table is not None
    assert node._rate_limit_ok("peer-a", MSG_PING) is True
    assert node._rate_limit_ok("peer-a", "attestation") is True
    assert node._rate_limit_ok("peer-a", "attestation") is True
    assert node._rate_limit_ok("peer-a", "attestation") is True
    assert node._rate_limit_ok("peer-a", "attestation") is False
    assert node.get_p2p_security_status().get("native_rate_limit_table") is True


def test_wiring():
    text = Path("network/p2p_node.py").read_text(encoding="utf-8")
    assert "P2PRateLimitTable" in text
    assert "_rl_table" in text
    assert (ROOT / "native/abs_native/src/p2p_rate_limit.rs").is_file()
