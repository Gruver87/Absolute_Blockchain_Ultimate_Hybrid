#!/usr/bin/env python3
"""ADR 0008 — mixed-network dual-stack (v1 NDJSON peers + v2 Borsh peers).

Emulates a heterogeneous mesh: some peers speak legacy JSON envelopes, others
speak AB2 Borsh lines. The node must:
  * auto-detect inbound codec
  * reply in the peer's native codec without manual config
  * preserve tip_safety / dispatch barriers (same msg_type+data after admit)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto.native import native_available
from network.p2p_dispatch import (
    DispatchOutcome,
    TipSafetyEvidenceBridge,
    build_default_dispatcher,
)
from network.p2p_dispatch.constants import MSG_NEW_BLOCK, MSG_STATUS
from network.transport.native_adapter import NativeTransportAdapter
from network.transport.types import OutboundEnvelope

pytestmark = pytest.mark.skipif(
    not native_available(),
    reason="abs_native not installed",
)


def _encode(msg_type: str, data: Any, codec: str) -> bytes:
    import abs_native as n  # type: ignore

    data_json = "null" if data is None else json.dumps(data, separators=(",", ":"))
    if codec == "v2":
        return bytes(n.encode_p2p_wire_message_v2(msg_type, data_json))
    return bytes(n.encode_p2p_wire_message(msg_type, data_json))


class _FakePeer:
    def __init__(self, peer_id: str = "peer-1") -> None:
        self.peer_id = peer_id
        self.host = "127.0.0.1"
        self.port = 1
        self.listen_port = 1
        self.height = 0
        self.head = ""
        self.sent: List[tuple] = []

    async def send(self, msg_type: str, data: Any = None) -> bool:
        self.sent.append((msg_type, data))
        return True


class _FakeHost:
    def __init__(self) -> None:
        self.config = MagicMock()
        self.config.p2p_discovery_allow_private = False
        self.config.p2p_peers_solicit_only = True
        self.config.p2p_height_cap_clear_head = True
        self.config.p2p_status_head_requires_height = True
        self.blockchain = MagicMock()
        self.blockchain.get_height = MagicMock(return_value=10)
        self.blockchain.get_block = MagicMock(return_value={"height": 5})
        self.peers: Dict[str, Any] = {}
        self.strikes: List[str] = []
        self.removed: List[str] = []
        self.counters: Dict[str, int] = {}
        self.new_block_calls: List[Any] = []

    def head(self) -> Optional[str]:
        return "aa" * 32

    def strike_peer(self, peer: Any, reason: str) -> bool:
        self.strikes.append(str(reason))
        return False

    def remove_peer(self, peer_id: str, peer: Any = None) -> None:
        self.removed.append(str(peer_id))

    def bump_counter(self, name: str, delta: int = 1) -> None:
        self.counters[name] = int(self.counters.get(name, 0)) + int(delta)

    async def handle_new_block(self, peer: Any, data: Any) -> None:
        self.new_block_calls.append(data)

    async def handle_status(self, peer: Any, data: Any) -> None:
        return None

    def get_block_future_refuse_reason(self, height: int) -> str:
        return ""

    def cap_claimed_peer_height(self, height: int) -> tuple:
        return int(height), False

    def status_head_height_refuse_reason(self, head_hash: str, height: int) -> str:
        return ""

    def ingest_discovered_peers(self, peer: Any, data: Any) -> None:
        return None

    def state_root_response_for_height(self, height: int) -> Any:
        return {"height": height, "state_root": "00" * 32, "head_hash": "aa" * 32}


def test_mixed_peers_auto_reply_in_native_codec():
    """Peer A speaks v1, peer B speaks v2 — outbound follows each peer."""
    import abs_native as n  # type: ignore

    ad = NativeTransportAdapter(wire_codec="auto")
    assert ad.wire_codec == "auto"

    line_v1 = _encode("ping", {"ts": 1.0}, "v1")
    d1 = ad.admit_inbound_line(
        line_v1, peer_id="peer-v1", now=1.0, allowed_types=["ping", "pong", "status"]
    )
    assert d1.accepted
    assert d1.frame is not None
    assert d1.frame.wire_codec == "v1"
    assert ad.resolve_outbound_codec(d1.frame.wire_codec) == "v1"

    line_v2 = _encode("ping", {"ts": 2.0}, "v2")
    d2 = ad.admit_inbound_line(
        line_v2, peer_id="peer-v2", now=2.0, allowed_types=["ping", "pong", "status"]
    )
    assert d2.accepted
    assert d2.frame is not None
    assert d2.frame.wire_codec == "v2"
    assert ad.resolve_outbound_codec(d2.frame.wire_codec) == "v2"

    prep_v1 = ad.prepare_outbound(
        OutboundEnvelope(peer_id="peer-v1", msg_type="pong", payload={"ts": 1.0}),
        now=3.0,
        data_json='{"ts":1.0}',
        peer_wire_codec="v1",
        allowed_types=["ping", "pong"],
    )
    assert prep_v1.accepted and prep_v1.frame is not None
    payload_v1 = bytes(prep_v1.frame.data["payload"])
    assert not payload_v1.startswith(b"AB2:")
    assert payload_v1.startswith(b"{")

    prep_v2 = ad.prepare_outbound(
        OutboundEnvelope(peer_id="peer-v2", msg_type="pong", payload={"ts": 2.0}),
        now=4.0,
        data_json='{"ts":2.0}',
        peer_wire_codec="v2",
        allowed_types=["ping", "pong"],
    )
    assert prep_v2.accepted and prep_v2.frame is not None
    payload_v2 = bytes(prep_v2.frame.data["payload"])
    assert payload_v2.startswith(b"AB2:")

    p1 = n.parse_p2p_wire_line(payload_v1)
    p2 = n.parse_p2p_wire_line(payload_v2)
    assert p1["type"] == "pong" and p1["wire_codec"] == "v1"
    assert p2["type"] == "pong" and p2["wire_codec"] == "v2"


def test_mixed_batch_ingress_preserves_payload_for_dispatch():
    """10 interleaved v1/v2 status frames → identical data after admit."""
    ad = NativeTransportAdapter(wire_codec="auto")
    frames: List[Tuple[str, Dict[str, Any]]] = []
    for i in range(10):
        codec = "v2" if i % 2 else "v1"
        data = {"height": i, "head_hash": "ab" * 32}
        line = _encode("status", data, codec)
        decision = ad.admit_inbound_line(
            line,
            peer_id=f"peer-{codec}-{i}",
            now=float(i + 1),
            allowed_types=["status", "ping", "pong", "new_block"],
        )
        assert decision.accepted and decision.frame is not None
        assert decision.frame.wire_codec == codec
        assert decision.frame.msg_type == "status"
        assert decision.frame.data["height"] == i
        frames.append((codec, decision.frame.data))

    assert sum(1 for c, _ in frames if c == "v1") == 5
    assert sum(1 for c, _ in frames if c == "v2") == 5


@pytest.mark.asyncio
async def test_v2_new_block_still_hits_tip_safety_gate():
    """v2-encoded new_block must still be refused by tip_evidence enforce."""
    ad = NativeTransportAdapter(wire_codec="auto")
    # Incomplete block → tip evidence validation fail under enforce
    line = _encode("new_block", {"height": 99}, "v2")
    decision = ad.admit_inbound_line(
        line,
        peer_id="peer-v2-block",
        now=10.0,
        allowed_types=["new_block", "status", "ping"],
    )
    assert decision.accepted and decision.frame is not None
    assert decision.frame.wire_codec == "v2"
    assert decision.frame.msg_type == MSG_NEW_BLOCK

    shadow = MagicMock()
    shadow.enabled = True
    shadow.enforce = True
    shadow.tip_state = None
    bridge = TipSafetyEvidenceBridge(shadow_provider=lambda: shadow)
    disp = build_default_dispatcher(tip_evidence=bridge)
    host = _FakeHost()
    peer = _FakePeer("peer-v2-block")

    out = await disp.dispatch(host, peer, MSG_NEW_BLOCK, decision.frame.data)
    assert out is DispatchOutcome.REFUSED
    assert host.new_block_calls == []
    assert host.counters.get("dispatch_tip_evidence_refuse_total") == 1
    assert host.strikes


@pytest.mark.asyncio
async def test_v1_and_v2_status_both_reach_dispatcher():
    ad = NativeTransportAdapter(wire_codec="auto")
    disp = build_default_dispatcher()
    host = _FakeHost()

    for codec in ("v1", "v2"):
        line = _encode("status", {"height": 9, "head_hash": "cc" * 32}, codec)
        d = ad.admit_inbound_line(
            line,
            peer_id=f"p-{codec}",
            now=1.0,
            allowed_types=["status"],
        )
        assert d.accepted and d.frame is not None
        assert d.frame.wire_codec == codec
        peer = _FakePeer(f"p-{codec}")
        out = await disp.dispatch(host, peer, MSG_STATUS, d.frame.data)
        assert out in (DispatchOutcome.HANDLED, DispatchOutcome.UNHANDLED)

    assert disp.status()["dispatch_total"] >= 1


def test_parse_exposes_wire_codec_for_security_pipeline():
    import abs_native as n  # type: ignore

    frame_v2 = _encode("ping", None, "v2")
    assert n.p2p_wire_detect_codec(frame_v2) == "v2"
    parsed = n.parse_p2p_wire_line(frame_v2)
    assert parsed["wire_codec"] == "v2"
    assert parsed["type"] == "ping"
    # Same type/data contract as v1 — tip_safety/dispatch never see the binary envelope.
    frame_v1 = _encode("ping", None, "v1")
    p1 = n.parse_p2p_wire_line(frame_v1)
    assert p1["type"] == parsed["type"]
