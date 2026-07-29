#!/usr/bin/env python3
"""Unit tests for P2P transport reject taxonomy."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.transport.reject import RejectCounters, classify_reason, make_reject
from network.transport.types import TransportRejectClass


def test_classify_exact_frame() -> None:
    assert classify_reason("p2p_line_too_large") is TransportRejectClass.FRAME
    assert classify_reason("bad_wire_line") is TransportRejectClass.FRAME


def test_classify_rate_and_egress() -> None:
    assert classify_reason("rate_limited") is TransportRejectClass.RATE
    assert classify_reason("rate_limit_exceeded") is TransportRejectClass.RATE
    assert classify_reason("exempt_rate_exceeded") is TransportRejectClass.RATE
    assert classify_reason("bandwidth_exceeded") is TransportRejectClass.RATE
    assert classify_reason("egress_bandwidth_exceeded") is TransportRejectClass.EGRESS
    assert classify_reason("egress_rate_limited") is TransportRejectClass.EGRESS
    assert classify_reason("prepare_failed") is TransportRejectClass.EGRESS
    assert classify_reason("ingress_error") is TransportRejectClass.INTERNAL
    assert classify_reason("recv_error") is TransportRejectClass.INTERNAL


def test_classify_wire_shape_prefix() -> None:
    assert classify_reason("p2p_type_not_allowed:FOO") is TransportRejectClass.WIRE_SHAPE
    assert classify_reason("p2p_missing_type") is TransportRejectClass.WIRE_SHAPE


def test_classify_empty_is_internal() -> None:
    assert classify_reason("") is TransportRejectClass.INTERNAL
    assert classify_reason("   ") is TransportRejectClass.INTERNAL
    assert classify_reason("totally_unknown_xyz") is TransportRejectClass.INTERNAL


def test_make_reject_sets_class() -> None:
    r = make_reject("bandwidth_exceeded", "peer hot")
    assert r.reason_code == "bandwidth_exceeded"
    assert r.reject_class is TransportRejectClass.RATE
    assert r.detail == "peer hot"


def test_reject_counters_status() -> None:
    c = RejectCounters()
    c.record_admit_ok()
    c.record_egress_ok()
    c.record_reject(make_reject("rate_limited"))
    c.record_reject(make_reject("p2p_line_too_large"))
    st = c.as_status()
    assert st["transport_boundary"] is True
    assert st["transport_admit_ok_total"] == 1
    assert st["transport_egress_ok_total"] == 1
    assert st["transport_reject_total"] == 2
    assert st["transport_reject_by_reason"]["rate_limited"] == 1
    assert st["transport_reject_by_class"]["rate"] == 1
    assert st["transport_reject_by_class"]["frame"] == 1
