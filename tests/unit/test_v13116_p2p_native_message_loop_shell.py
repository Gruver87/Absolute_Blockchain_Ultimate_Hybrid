#!/usr/bin/env python3
"""v1.3.116: native message-loop event shell (dispatch/strike ordered)."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native
from network.p2p_node import MSG_STATUS, P2PNode, PeerConnection
from runtime.config import Config


def _wire(msg_type: str, data: dict) -> bytes:
    return (
        json.dumps(
            {"type": msg_type, "data": data},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def test_needles_v13116():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "read_message_loop_events" in transport
    assert "LoopShellEvent" in transport
    assert "v1.3.116" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "recv_loop_events" in p2p
    assert "native_message_loop_shell" in p2p
    assert "read_message_loop_events" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.116.md").read_text(encoding="utf-8")
    assert "1.3.116-industrial" in notes
    assert Config().node_version == "1.3.116-industrial"
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_message_loop_shell" in metrics
    assert "abs_p2p_native_message_loop_dispatch_total" in metrics
    assert "abs_p2p_native_message_loop_strikes_total" in metrics


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_events_dispatch_then_strike():
    listener = native.P2PNativeListener("127.0.0.1", 0, 1024 * 1024, 5000)
    addr = listener.local_addr
    host, port_s = addr.rsplit(":", 1)
    port = int(port_s)
    host = host.strip("[]")
    got = {}

    def server():
        deadline = time.time() + 8.0
        while time.time() < deadline:
            out = listener.accept()
            if out.get("ok") and out.get("conn") is not None:
                c = out["conn"]
                c.set_session_established(True)
                got["out"] = c.read_message_loop_events(
                    8, 65536, ["status", "handshake", "new_tx"], False
                )
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    good = _wire(
        "status",
        {"height": 1, "head_hash": "aa", "peer_count": 0},
    )
    bad = _wire("handshake", {"chain_id": 1, "height": 0, "node_id": "x"})
    conn.write(good + bad)
    conn.close()
    t.join(timeout=5)
    assert got.get("out", {}).get("ok") is True
    events = list(got["out"].get("events") or [])
    assert any(e.get("action") == "dispatch" and e.get("type") == "status" for e in events)
    assert any(
        e.get("action") == "strike" and e.get("reason") == "mid_session_handshake"
        for e in events
    )
    # Ordered: dispatch before strike
    di = next(i for i, e in enumerate(events) if e.get("action") == "dispatch")
    si = next(i for i, e in enumerate(events) if e.get("action") == "strike")
    assert di < si


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_events_idle_on_timeout():
    listener = native.P2PNativeListener("127.0.0.1", 0, 1024 * 1024, 200)
    addr = listener.local_addr
    host, port_s = addr.rsplit(":", 1)
    port = int(port_s)
    host = host.strip("[]")
    got = {}

    def server():
        deadline = time.time() + 8.0
        while time.time() < deadline:
            out = listener.accept()
            if out.get("ok") and out.get("conn") is not None:
                c = out["conn"]
                c.set_timeout_ms(200)
                got["out"] = c.read_message_loop_events(8, 65536, ["status"], False)
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    # No write — server times out → idle
    time.sleep(0.5)
    conn.close()
    t.join(timeout=5)
    assert got.get("out", {}).get("ok") is True
    events = list(got["out"].get("events") or [])
    assert any(e.get("action") == "idle" for e in events)


@pytest.mark.asyncio
async def test_message_loop_shell_dispatches_and_strikes():
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.p2p_tls_enabled = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_rate_limit_strikes = 5
    node = P2PNode(cfg, MagicMock(), MagicMock())
    node._native_message_loop_shell = True
    node._running = True
    peer = PeerConnection(None, None, peer_id="shell-peer")
    peer.host = "127.0.0.1"
    peer.port = 9
    peer._native_conn = MagicMock()
    node.peers[peer.peer_id] = peer

    async def fake_events(*_a, **_k):
        if not hasattr(fake_events, "n"):
            fake_events.n = 0
        fake_events.n += 1
        if fake_events.n == 1:
            return [
                {"action": "dispatch", "type": MSG_STATUS, "data": {"height": 1}},
                {"action": "strike", "reason": "bad_status_payload"},
            ]
        return [{"action": "eof"}]

    peer.recv_loop_events = fake_events  # type: ignore[method-assign]
    node._handle_message = AsyncMock()  # type: ignore[method-assign]
    strikes = []

    def capture_strike(p, reason):
        strikes.append(reason)
        return True  # disconnect after strike

    node._strike_peer_sync = capture_strike  # type: ignore[method-assign]
    await node._message_loop(peer)
    node._handle_message.assert_awaited_once()
    assert strikes == ["bad_status_payload"]
    assert int(node._native_message_loop_dispatch_total) == 1
    assert int(node._native_message_loop_strikes_total) == 1
