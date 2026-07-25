#!/usr/bin/env python3
"""v1.3.115: native handshake policy fuse (chain_id + TLS identity) + Max-gate ready fix."""

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
        "chain_id": 778888,
        "height": 0,
        "head_hash": "",
        "node_id": "n1",
        "p2p_port": 5000,
    },
    separators=(",", ":"),
)
BAD_CHAIN_HS = json.dumps(
    {
        "chain_id": 1,
        "height": 0,
        "head_hash": "",
        "node_id": "n1",
        "p2p_port": 5000,
    },
    separators=(",", ":"),
)


def test_needles_v13115():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "check_handshake_policy" in transport
    assert "chain_id_mismatch" in transport
    assert "tls_identity_mismatch" in transport
    assert "v1.3.115" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_policy_applied" in p2p
    assert "native_handshake_policy_gate" in p2p
    http_py = (ROOT / "api" / "http.py").read_text(encoding="utf-8")
    assert 'getattr(p2p, "_native_listener", None) is not None' in http_py
    notes = (ROOT / "RELEASE_NOTES_v1.3.115.md").read_text(encoding="utf-8")
    assert "1.3.115-industrial" in notes
    # Live Config().node_version advances with later waves; pin notes not config.
    assert "abs_p2p_native_handshake_policy_gate" in (
        ROOT / "observability" / "metrics.py"
    ).read_text(encoding="utf-8")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_handshake_rejects_chain_id_mismatch():
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
                got["out"] = c.handshake_roundtrip(
                    False, GOOD_HS, 65536, 778888, False, False
                )
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    # Initiator with wrong chain_id vs responder expected_chain_id
    out = conn.handshake_roundtrip(True, BAD_CHAIN_HS, 65536, 778888, False, False)
    conn.close()
    t.join(timeout=5)
    # Responder should reject initiator's bad chain before writing ack, or
    # initiator sees reject from peer policy — at least one side fails closed.
    assert got.get("out", {}).get("ok") is False
    assert got["out"].get("reason") == "chain_id_mismatch"
    # Initiator may still get EOF / fail depending on timing; policy on responder is enough.


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_handshake_policy_accepts_matching_chain():
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
                got["out"] = c.handshake_roundtrip(
                    False, GOOD_HS, 65536, 778888, False, False
                )
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    out = conn.handshake_roundtrip(True, GOOD_HS, 65536, 778888, False, False)
    conn.close()
    t.join(timeout=5)
    assert out.get("ok") is True
    assert got.get("out", {}).get("ok") is True


def test_p2p_node_wires_policy_kwargs():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "int(self.config.chain_id)" in p2p
    assert "native_policy_applied" in p2p
    cfg = Config()
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert "native_handshake_policy_gate" in node.get_p2p_security_status()
