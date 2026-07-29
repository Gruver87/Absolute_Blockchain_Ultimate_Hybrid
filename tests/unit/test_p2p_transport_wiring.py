#!/usr/bin/env python3
"""Step C: live NativeTransportAdapter wiring into P2PNode / PeerConnection."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import PeerConnection, WireReject
from network.transport import (
    AdmitDecision,
    InboundFrame,
    NativeTransportAdapter,
    TransportReject,
    TransportRejectClass,
    make_reject,
)
from runtime.config import Config


def _minimal_node():
    from network.p2p_node import P2PNode

    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = False
    chain = MagicMock()
    chain.height = 0
    chain.get_tip_hash = MagicMock(return_value="")
    mp = MagicMock()
    return P2PNode(cfg, chain, mp)


def test_node_owns_transport_adapter() -> None:
    node = _minimal_node()
    assert isinstance(node.transport_adapter, NativeTransportAdapter)
    st = node.get_p2p_security_status()
    assert st.get("transport_boundary") is True
    assert "transport_admit_ok_total" in st
    assert "transport_reject_total" in st


def test_attach_peer_hooks_assigns_adapter() -> None:
    node = _minimal_node()
    peer = PeerConnection(None, None)
    node._attach_peer_hooks(peer)
    assert peer._transport_adapter is node.transport_adapter


def test_prepare_outbound_uses_adapter_ok() -> None:
    node = _minimal_node()
    peer = PeerConnection(None, None)
    node._attach_peer_hooks(peer)
    peer._use_egress_prepare = True
    peer.peer_id = "peer-a"
    payload = b'{"type":"ping","data":null}\n'
    decision = AdmitDecision(
        ok=True,
        frame=InboundFrame(
            peer_id="peer-a",
            msg_type="ping",
            data={"payload": payload},
            raw_len=len(payload),
        ),
    )
    adapter = MagicMock()
    adapter.prepare_outbound = MagicMock(return_value=decision)
    peer._transport_adapter = adapter
    out = peer._prepare_outbound("ping", None)
    assert out == payload
    assert adapter.prepare_outbound.called
    kwargs = adapter.prepare_outbound.call_args.kwargs
    assert kwargs.get("data_json") == "null"


def test_prepare_outbound_adapter_reject_returns_none() -> None:
    node = _minimal_node()
    peer = PeerConnection(None, None)
    node._attach_peer_hooks(peer)
    peer._use_egress_prepare = True
    peer.peer_id = "peer-a"
    decision = AdmitDecision(
        ok=False,
        reject=TransportReject(
            reason_code="egress_bandwidth_exceeded",
            reject_class=TransportRejectClass.EGRESS,
        ),
    )
    bumped = {"n": 0}

    def _bump() -> None:
        bumped["n"] += 1

    peer._on_egress_reject = _bump
    adapter = MagicMock()
    adapter.prepare_outbound = MagicMock(return_value=decision)
    peer._transport_adapter = adapter
    out = peer._prepare_outbound("ping", {"x": 1})
    assert out is None
    assert bumped["n"] == 1


@pytest.mark.asyncio
async def test_recv_ingress_uses_adapter_reject() -> None:
    node = _minimal_node()
    peer = PeerConnection(None, None)
    node._attach_peer_hooks(peer)
    peer.peer_id = "peer-b"
    reject = make_reject("rate_limit_exceeded")
    decision = AdmitDecision(ok=False, reject=reject)

    async def _fake_line(_limit: int):
        return b'{"type":"ping","data":null}\n'

    adapter = MagicMock()
    adapter.admit_inbound_line = MagicMock(return_value=decision)
    # Real counters still live on node.transport_adapter for status merge.
    node.transport_adapter.counters.record_reject(reject)
    peer._transport_adapter = adapter
    with patch.object(peer, "_read_wire_line", side_effect=_fake_line):
        out = await peer.recv(
            use_ingress=True,
            rl_table=MagicMock(),
            peer_key="peer-b",
        )
    assert isinstance(out, WireReject)
    assert out.reason == "rate_limit_exceeded"
    assert adapter.admit_inbound_line.called
    st = node.get_p2p_security_status()
    assert st["transport_reject_by_reason"].get("rate_limit_exceeded") == 1
    assert st["transport_reject_by_class"].get("rate") == 1


@pytest.mark.asyncio
async def test_recv_ingress_uses_adapter_ok() -> None:
    node = _minimal_node()
    peer = PeerConnection(None, None)
    node._attach_peer_hooks(peer)
    peer.peer_id = "peer-c"
    frame = InboundFrame(peer_id="peer-c", msg_type="ping", data={}, raw_len=10)
    decision = AdmitDecision(ok=True, frame=frame)

    async def _fake_line(_limit: int):
        return b'{"type":"ping","data":{}}\n'

    adapter = MagicMock()
    adapter.admit_inbound_line = MagicMock(return_value=decision)
    peer._transport_adapter = adapter
    with patch.object(peer, "_read_wire_line", side_effect=_fake_line):
        out = await peer.recv(
            use_ingress=True,
            rl_table=MagicMock(),
            peer_key="peer-c",
        )
    assert isinstance(out, dict)
    assert out["type"] == "ping"
    assert out["data"] == {}


def test_classify_live_reason_codes() -> None:
    from network.transport import classify_reason

    assert classify_reason("rate_limit_exceeded") is TransportRejectClass.RATE
    assert classify_reason("exempt_rate_exceeded") is TransportRejectClass.RATE
    assert classify_reason("ingress_error") is TransportRejectClass.INTERNAL
    assert classify_reason("recv_error") is TransportRejectClass.INTERNAL
    assert classify_reason("prepare_failed") is TransportRejectClass.EGRESS


def test_prepare_outbound_data_json_passthrough() -> None:
    ad = NativeTransportAdapter(require_native=False)
    from network.transport import OutboundEnvelope

    env = OutboundEnvelope(peer_id="p1", msg_type="ping", payload={"ignored": True})
    captured = {}

    def _fake_prepare(msg_type, data_json, peer_id, now, max_bytes, allowed_types, rl):
        captured["data_json"] = data_json
        return {"ok": True, "payload": b"x\n"}

    with patch("crypto.native.native_available", return_value=True), patch(
        "crypto.native.p2p_egress_prepare", side_effect=_fake_prepare
    ):
        d = ad.prepare_outbound(
            env,
            now=1.0,
            data_json='{"hello":"мир"}',
        )
    assert d.accepted is True
    assert captured["data_json"] == '{"hello":"мир"}'
