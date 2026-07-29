#!/usr/bin/env python3
"""ADR 0008 — transport dual-stack wire codec (v1 NDJSON / v2 AB2 Borsh)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto.native import native_available
from network.transport.native_adapter import NativeTransportAdapter

pytestmark = pytest.mark.skipif(
    not native_available(),
    reason="abs_native not installed",
)


def test_encode_v2_line_roundtrip_via_parse():
    import abs_native as n  # type: ignore

    assert hasattr(n, "encode_p2p_wire_message_v2")
    frame = n.encode_p2p_wire_message_v2("new_tx", '{"hash":"abc"}')
    assert bytes(frame).startswith(b"AB2:")
    assert n.p2p_wire_detect_codec(bytes(frame)) == "v2"
    parsed = n.parse_p2p_wire_line(bytes(frame))
    assert parsed is not None
    assert parsed["type"] == "new_tx"
    assert parsed["data"]["hash"] == "abc"


def test_ingress_admits_v2_line():
    import abs_native as n  # type: ignore

    frame = n.encode_p2p_wire_message_v2("ping", "null")
    ad = NativeTransportAdapter(wire_codec="v1")  # inbound auto-detect
    # Use adapter admit which calls p2p_ingress_admit
    d = ad.admit_inbound_line(
        bytes(frame),
        peer_id="peer-v2",
        now=1.0,
        allowed_types=["ping", "pong", "new_tx", "status"],
    )
    assert d.accepted is True
    assert d.frame is not None
    assert d.frame.msg_type == "ping"


def test_adapter_prepare_outbound_v2_payload_prefix(monkeypatch):
    ad = NativeTransportAdapter(wire_codec="v2")
    assert ad.wire_codec == "v2"
    assert ad.capability_status()["wire_codec"] == "v2"

    from network.transport.types import OutboundEnvelope

    called = {}

    def fake_prepare(*args, **kwargs):
        called["codec"] = kwargs.get("codec") or (args[7] if len(args) > 7 else None)
        payload = b"AB2:deadbeef\n"
        return {"ok": True, "payload": payload, "nbytes": len(payload)}

    monkeypatch.setattr("crypto.native.native_available", lambda: True)
    monkeypatch.setattr("crypto.native.p2p_egress_prepare", fake_prepare)

    d = ad.prepare_outbound(
        OutboundEnvelope(peer_id="p1", msg_type="ping", payload={}),
        now=1.0,
        data_json="null",
    )
    assert d.accepted is True
    assert called.get("codec") == "v2"
    assert d.frame is not None
    assert bytes(d.frame.data["payload"]).startswith(b"AB2:")


def test_default_codec_is_auto_peer_aware():
    ad = NativeTransportAdapter()
    assert ad.wire_codec == "auto"
    assert ad.resolve_outbound_codec("v1") == "v1"
    assert ad.resolve_outbound_codec("v2") == "v2"
