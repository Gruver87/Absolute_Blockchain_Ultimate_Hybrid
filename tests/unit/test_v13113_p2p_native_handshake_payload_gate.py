#!/usr/bin/env python3
"""v1.3.113: native handshake payload gate on handshake_roundtrip."""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native
from network.p2p_node import P2PNode
from runtime.config import Config

GOOD_HS = json.dumps(
    {
        "chain_id": 1,
        "height": 0,
        "head_hash": "aa",
        "node_id": "n1",
        "p2p_port": 5000,
    },
    separators=(",", ":"),
)


def test_needles_v13113():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "check_handshake_payload" in transport
    assert "bad_handshake_payload" in transport
    assert "v1.3.113" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_handshake_payload_gate" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.113.md").read_text(encoding="utf-8")
    assert "1.3.113-industrial" in notes
    assert Config().node_version == "1.3.113-industrial"
    assert "abs_p2p_native_handshake_payload_gate" in (
        ROOT / "observability" / "metrics.py"
    ).read_text(encoding="utf-8")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_handshake_rejects_bad_payload():
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
                # Responder: peer sends malformed handshake
                got["out"] = c.handshake_roundtrip(False, GOOD_HS, 65536)
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    # Initiator path: write bad handshake via roundtrip's own write — instead
    # write a bad handshake frame directly so responder sees bad shape.
    conn.write_message("handshake", "{}", ["handshake", "handshake_ack"])
    time.sleep(0.2)
    conn.close()
    t.join(timeout=3)
    listener.close()

    out = got.get("out") or {}
    assert out.get("ok") is False, out
    assert out.get("reason") == "bad_handshake_payload"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_handshake_allows_well_shaped():
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
                got["out"] = c.handshake_roundtrip(False, GOOD_HS, 65536)
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    out = conn.handshake_roundtrip(True, GOOD_HS, 65536)
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()

    assert out.get("ok") is True, out
    assert out.get("type") == "handshake_ack"
    assert (got.get("out") or {}).get("ok") is True


def test_p2p_node_native_handshake_payload_gate_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node.get_p2p_security_status().get("native_handshake_payload_gate") is True
