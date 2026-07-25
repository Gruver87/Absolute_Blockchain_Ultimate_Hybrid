#!/usr/bin/env python3
"""v1.3.93: native wire encode + write pump (P2PNativeConn.write_message)."""

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


def test_needles_v1393():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "write_message" in transport
    assert "v1.3.93" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_write_message" in p2p
    assert "write_message" in p2p
    assert "_native_write_message" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "1.3.93-industrial" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.93.md").read_text(encoding="utf-8")
    assert "1.3.93-industrial" in notes
    assert Config().node_version == "1.3.93-industrial"
    assert hasattr(abs_native.P2PNativeConn, "write_message")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_write_message_roundtrip():
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
                    w = c.write_message("pong", '{"ok":true}', ["ping", "pong"])
                    got["write"] = w
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    sent = conn.write_message("ping", "null", ["ping", "pong"])
    assert sent.get("ok") is True, sent
    reply = conn.read_message(65536, ["ping", "pong"])
    assert reply.get("ok") is True, reply
    assert reply.get("type") == "pong"
    conn.close()
    listener.close()
    t.join(timeout=3)
    assert got.get("msg", {}).get("type") == "ping"
    assert got.get("write", {}).get("ok") is True


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_write_message_rejects_disallowed_type():
    listener = native.P2PNativeListener("127.0.0.1", 0, 1024 * 1024, 5000)
    addr = listener.local_addr
    host, port_s = addr.rsplit(":", 1)
    port = int(port_s)
    host = host.strip("[]")
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    out = conn.write_message("evil", "null", ["status"])
    assert out.get("ok") is False
    assert "p2p_type_not_allowed" in str(out.get("reason") or "")
    conn.close()
    listener.close()


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_native_write_message_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._use_native_transport is True
    assert node._native_write_message is True
    status = node.get_p2p_security_status()
    assert status.get("native_write_message") is True
