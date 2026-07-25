#!/usr/bin/env python3
"""v1.3.98: native read-path auto-pong keepalive."""

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


def test_needles_v1398():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "auto_pong" in transport
    assert "maybe_auto_pong" in transport
    assert "v1.3.98" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_native_auto_pong" in p2p
    assert "p2p_native_auto_pong" in (ROOT / "runtime" / "config.py").read_text(
        encoding="utf-8"
    )
    notes = (ROOT / "RELEASE_NOTES_v1.3.98.md").read_text(encoding="utf-8")
    assert "1.3.98-industrial" in notes
    assert Config().node_version == "1.3.98-industrial"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_auto_pong_roundtrip():
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
                # auto_pong=True: ping is answered and omitted from batch
                batch = c.read_messages(8, 65536, ["ping", "pong", "status"], True)
                got["batch"] = batch
                got["auto_pongs"] = int(c.auto_pongs or 0)
                # Next message should be status after ping was consumed
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write_message("ping", '{"ts":1.0}', ["ping", "pong", "status"])
    # Client should receive auto-pong
    reply = conn.read_message(65536, ["ping", "pong", "status"], False)
    assert reply.get("ok") is True, reply
    assert reply.get("type") == "pong"
    conn.write_message("status", '{"height":1}', ["ping", "pong", "status"])
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()

    batch = got.get("batch") or {}
    assert batch.get("ok") is True, batch
    assert int(batch.get("auto_pongs") or 0) >= 1
    msgs = list(batch.get("messages") or [])
    assert any(m.get("type") == "status" for m in msgs)
    assert not any(m.get("type") == "ping" for m in msgs)
    assert int(got.get("auto_pongs") or 0) >= 1


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_native_auto_pong_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_native_auto_pong = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._native_auto_pong is True
    assert node.get_p2p_security_status().get("native_auto_pong") is True
