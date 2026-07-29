#!/usr/bin/env python3
"""Unit tests for P2P transport types and ports."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.transport.errors import TransportValidationError
from network.transport.ports import PeerAdmitPort, TransportCapabilityPort
from network.transport.types import (
    AdmitDecision,
    InboundFrame,
    OutboundEnvelope,
    PeerEndpoint,
    TransportReject,
    TransportRejectClass,
)


def test_peer_endpoint_ok() -> None:
    ep = PeerEndpoint(host="127.0.0.1", port=30303, peer_id="a")
    assert ep.host == "127.0.0.1"
    assert ep.port == 30303


def test_peer_endpoint_rejects_bad_port() -> None:
    with pytest.raises(TransportValidationError):
        PeerEndpoint(host="127.0.0.1", port=0)
    with pytest.raises(TransportValidationError):
        PeerEndpoint(host="127.0.0.1", port=70000)
    with pytest.raises(TransportValidationError):
        PeerEndpoint(host="", port=1)


def test_peer_endpoint_rejects_bool_port() -> None:
    with pytest.raises(TransportValidationError):
        PeerEndpoint(host="127.0.0.1", port=True)  # type: ignore[arg-type]


def test_inbound_frame_and_admit_decision() -> None:
    frame = InboundFrame(peer_id="p1", msg_type="PING", data={}, raw_len=12)
    ok = AdmitDecision(ok=True, frame=frame)
    bad = AdmitDecision(
        ok=False,
        reject=TransportReject(
            reason_code="rate_limited",
            reject_class=TransportRejectClass.RATE,
        ),
    )
    assert ok.accepted is True
    assert bad.accepted is False


def test_outbound_envelope() -> None:
    env = OutboundEnvelope(peer_id="p1", msg_type="PONG", payload={"n": 1})
    assert env.msg_type == "PONG"
    assert env.payload["n"] == 1


def test_ports_are_runtime_checkable() -> None:
    class _Admit:
        def admit_inbound_line(self, line, *, peer_id, now, max_bytes=0, allowed_types=None, rate_table=None):
            return AdmitDecision(ok=False)

    class _Cap:
        def capability_status(self):
            return {}

        def require_transport(self):
            return None

    assert isinstance(_Admit(), PeerAdmitPort)
    assert isinstance(_Cap(), TransportCapabilityPort)
