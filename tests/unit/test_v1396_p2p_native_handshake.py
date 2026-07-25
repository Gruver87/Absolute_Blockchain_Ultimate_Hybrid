#!/usr/bin/env python3
"""v1.3.96: native handshake_roundtrip I/O fuse."""

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

import abs_native

from crypto import native
from network.p2p_node import P2PNode
from runtime.config import Config


def test_needles_v1396():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "handshake_roundtrip" in transport
    assert "v1.3.96" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "handshake_roundtrip" in p2p
    assert "_native_handshake" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_native_transport" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.96.md").read_text(encoding="utf-8")
    assert "1.3.96-industrial" in notes
    assert "1.3.96" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert hasattr(abs_native.P2PNativeConn, "handshake_roundtrip")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_handshake_roundtrip():
    listener = native.P2PNativeListener("127.0.0.1", 0, 1024 * 1024, 5000)
    addr = listener.local_addr
    host, port_s = addr.rsplit(":", 1)
    port = int(port_s)
    host = host.strip("[]")
    got = {}

    server_info = {
        "chain_id": 778888,
        "version": "1.3.96-industrial",
        "height": 1,
        "head_hash": "aa" * 32,
        "node_id": "ci-node-2",
        "p2p_port": port,
    }
    client_info = {
        "chain_id": 778888,
        "version": "1.3.96-industrial",
        "height": 2,
        "head_hash": "bb" * 32,
        "node_id": "ci-node-1",
        "p2p_port": 15080,
    }

    def server():
        deadline = time.time() + 8.0
        while time.time() < deadline:
            out = listener.accept()
            if out.get("ok") and out.get("conn") is not None:
                c = out["conn"]
                got["resp"] = c.handshake_roundtrip(
                    False, json.dumps(server_info, separators=(",", ":")), 65536
                )
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    init = conn.handshake_roundtrip(
        True, json.dumps(client_info, separators=(",", ":")), 65536
    )
    conn.close()
    t.join(timeout=3)
    listener.close()

    assert init.get("ok") is True, init
    assert init.get("type") == "handshake_ack"
    assert init.get("data", {}).get("node_id") == "ci-node-2"
    resp = got.get("resp") or {}
    assert resp.get("ok") is True, resp
    assert resp.get("type") == "handshake"
    assert resp.get("data", {}).get("node_id") == "ci-node-1"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_native_handshake_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._native_handshake is True
    assert node.get_p2p_security_status().get("native_handshake") is True
