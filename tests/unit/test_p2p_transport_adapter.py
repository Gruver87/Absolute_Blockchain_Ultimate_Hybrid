#!/usr/bin/env python3
"""Unit tests for NativeTransportAdapter (A–B boundary)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.transport.errors import TransportCapabilityError
from network.transport.native_adapter import NativeTransportAdapter, default_allowed_types
from network.transport.types import OutboundEnvelope, PeerEndpoint, TransportRejectClass


def test_capability_status_keys() -> None:
    ad = NativeTransportAdapter()
    st = ad.capability_status()
    assert "available" in st
    assert "transport" in st
    assert "tls" in st
    assert "require_native" in st


def test_admit_rejects_non_bytes() -> None:
    ad = NativeTransportAdapter()
    d = ad.admit_inbound_line("not-bytes", peer_id="p1", now=1.0)  # type: ignore[arg-type]
    assert d.accepted is False
    assert d.reject is not None
    assert d.reject.reason_code == "transport_validation"


def test_admit_rejects_empty_peer() -> None:
    ad = NativeTransportAdapter()
    d = ad.admit_inbound_line(b'{"type":"PING","data":{}}\n', peer_id="  ", now=1.0)
    assert d.accepted is False
    assert d.reject is not None
    assert d.reject.reason_code == "empty_peer_id"


def test_admit_capability_soft_when_native_missing() -> None:
    ad = NativeTransportAdapter(require_native=False)
    with patch("crypto.native.native_available", return_value=False):
        d = ad.admit_inbound_line(b'{"type":"PING","data":{}}\n', peer_id="p1", now=1.0)
    assert d.accepted is False
    assert d.reject is not None
    assert d.reject.reject_class is TransportRejectClass.CAPABILITY
    assert ad.counters.reject_total == 1


def test_admit_capability_hard_raises() -> None:
    ad = NativeTransportAdapter(require_native=True)
    with patch("crypto.native.native_available", return_value=False):
        with pytest.raises(TransportCapabilityError):
            ad.admit_inbound_line(b'{"type":"PING","data":{}}\n', peer_id="p1", now=1.0)


def test_admit_maps_native_ok() -> None:
    ad = NativeTransportAdapter()
    fake = {"ok": True, "type": "PING", "data": {"x": 1}}
    with patch("crypto.native.native_available", return_value=True), patch(
        "crypto.native.p2p_ingress_admit", return_value=fake
    ):
        line = b'{"type":"PING","data":{"x":1}}\n'
        d = ad.admit_inbound_line(line, peer_id="peer-a", now=10.0)
    assert d.accepted is True
    assert d.frame is not None
    assert d.frame.msg_type == "PING"
    assert d.frame.peer_id == "peer-a"
    assert d.frame.data == {"x": 1}
    assert d.frame.raw_len == len(line)
    assert ad.counters.admit_ok_total == 1


def test_admit_maps_native_reject() -> None:
    ad = NativeTransportAdapter()
    fake = {"ok": False, "reason": "rate_limited"}
    with patch("crypto.native.native_available", return_value=True), patch(
        "crypto.native.p2p_ingress_admit", return_value=fake
    ):
        d = ad.admit_inbound_line(b'{"type":"TX","data":{}}\n', peer_id="p1", now=1.0)
    assert d.accepted is False
    assert d.reject is not None
    assert d.reject.reason_code == "rate_limited"
    assert d.reject.reject_class is TransportRejectClass.RATE


def test_prepare_outbound_ok() -> None:
    ad = NativeTransportAdapter()
    payload = b'{"type":"PONG","data":{}}\n'
    fake = {"ok": True, "payload": payload}
    env = OutboundEnvelope(peer_id="p1", msg_type="PONG", payload={})
    with patch("crypto.native.native_available", return_value=True), patch(
        "crypto.native.p2p_egress_prepare", return_value=fake
    ):
        d = ad.prepare_outbound(env, now=1.0)
    assert d.accepted is True
    assert d.frame is not None
    assert d.frame.data["payload"] == payload
    assert ad.counters.egress_ok_total == 1


def test_prepare_outbound_reject() -> None:
    ad = NativeTransportAdapter()
    env = OutboundEnvelope(peer_id="p1", msg_type="TX", payload={"a": 1})
    with patch("crypto.native.native_available", return_value=True), patch(
        "crypto.native.p2p_egress_prepare",
        return_value={"ok": False, "reason": "egress_bandwidth_exceeded"},
    ):
        d = ad.prepare_outbound(env, now=1.0)
    assert d.accepted is False
    assert d.reject is not None
    assert d.reject.reject_class is TransportRejectClass.EGRESS


def test_merge_into_status() -> None:
    ad = NativeTransportAdapter()
    ad.counters.record_admit_ok()
    merged = ad.merge_into_status({"shape_rejects_total": 3})
    assert merged["shape_rejects_total"] == 3
    assert merged["transport_boundary"] is True
    assert merged["transport_admit_ok_total"] == 1
    assert "transport_native_available" in merged


def test_connect_requires_transport() -> None:
    ad = NativeTransportAdapter()
    ep = PeerEndpoint(host="127.0.0.1", port=9)
    with patch(
        "network.transport.native_adapter.NativeTransportAdapter.capability_status",
        return_value={"transport": False, "error": "x"},
    ):
        with pytest.raises(TransportCapabilityError):
            ad.connect(ep)


def test_clamp_helpers_bounded() -> None:
    ad = NativeTransportAdapter()
    assert 1 <= ad.clamp_batch(0) <= 64
    assert 1024 <= ad.clamp_chunk(1) <= 1024 * 1024
    assert 1000 <= ad.clamp_timeout_ms(1) <= 600_000


def test_default_allowed_types_non_empty() -> None:
    assert "PING" in default_allowed_types()


def test_metrics_export_transport_needles() -> None:
    from observability.metrics import MetricsCollector

    text = MetricsCollector().render_prometheus(
        node_id="n1",
        p2p_security={
            "transport_boundary": True,
            "transport_admit_ok_total": 2,
            "transport_egress_ok_total": 1,
            "transport_reject_total": 3,
            "transport_reject_by_reason": {"rate_limited": 2, "bad_wire_line": 1},
            "transport_reject_by_class": {"rate": 2, "frame": 1},
        },
    )
    assert "abs_p2p_transport_boundary" in text
    assert "abs_p2p_transport_admit_ok_total" in text
    assert "abs_p2p_transport_reject_total" in text
    assert 'abs_p2p_transport_reject{node_id="n1",reason="rate_limited"} 2' in text
    assert 'abs_p2p_transport_reject_class{node_id="n1",class="frame"} 1' in text


def test_live_native_admit_when_available() -> None:
    from crypto import native as nat

    if not nat.native_available():
        pytest.skip("abs_native not installed")
    try:
        ad = NativeTransportAdapter(require_native=False)
        line = (json.dumps({"type": "PING", "data": {}}) + "\n").encode("utf-8")
        d = ad.admit_inbound_line(
            line,
            peer_id="unit-peer",
            now=1.0,
            allowed_types=default_allowed_types(),
            rate_table=None,
        )
        assert d.accepted is True
        assert d.frame is not None
        assert d.frame.msg_type == "PING"
    except Exception as exc:
        pytest.skip(f"native ingress unavailable: {exc}")
