#!/usr/bin/env python3
"""v1.3.92: native framed read + wire-parse pump (P2PNativeConn.read_message)."""

from __future__ import annotations

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


def test_needles_v1392():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "read_message" in transport
    assert "v1.3.92" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "read_message" in p2p
    assert "_native_read_message" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "1.3.92-industrial" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.92.md").read_text(encoding="utf-8")
    assert "1.3.92-industrial" in notes
    assert Config().node_version == "1.3.92-industrial"
    assert hasattr(abs_native.P2PNativeConn, "read_message")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_read_message_roundtrip():
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
                msg = c.read_message(65536, ["ping", "pong"])
                got["msg"] = msg
                if msg.get("ok") and not msg.get("eof"):
                    c.write(b'{"type":"pong","data":{"ok":true}}\n')
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write(b'{"type":"ping","data":null}\n')
    reply = conn.read_message(65536, ["ping", "pong"])
    assert reply.get("ok") is True, reply
    assert reply.get("type") == "pong"
    assert reply.get("data", {}).get("ok") is True
    conn.close()
    listener.close()
    t.join(timeout=3)
    assert got.get("msg", {}).get("ok") is True
    assert got["msg"].get("type") == "ping"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_read_message_rejects_disallowed_type():
    listener = native.P2PNativeListener("127.0.0.1", 0, 1024 * 1024, 5000)
    addr = listener.local_addr
    host, port_s = addr.rsplit(":", 1)
    port = int(port_s)
    host = host.strip("[]")
    result = {}

    def server():
        deadline = time.time() + 8.0
        while time.time() < deadline:
            out = listener.accept()
            if out.get("ok") and out.get("conn") is not None:
                c = out["conn"]
                result["msg"] = c.read_message(65536, ["status"])
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write(b'{"type":"evil","data":null}\n')
    conn.close()
    t.join(timeout=3)
    listener.close()
    msg = result.get("msg") or {}
    assert msg.get("ok") is False
    assert "p2p_type_not_allowed" in str(msg.get("reason") or "")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_native_read_message_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._use_native_transport is True
    assert node._native_read_message is True
    status = node.get_p2p_security_status()
    assert status.get("native_read_message") is True
