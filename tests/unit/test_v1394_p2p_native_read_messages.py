#!/usr/bin/env python3
"""v1.3.94: native batch read_messages pump."""

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


def test_needles_v1394():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "read_messages" in transport
    assert "v1.3.94" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_pending_msgs" in p2p
    assert "read_messages" in p2p
    assert "_native_read_messages" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_native_transport" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.94.md").read_text(encoding="utf-8")
    assert "1.3.94-industrial" in notes
    assert "1.3.94" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert hasattr(abs_native.P2PNativeConn, "read_messages")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_read_messages_batch():
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
                batch = c.read_messages(8, 65536, ["ping", "status"])
                got["batch"] = batch
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write_message("ping", "null", ["ping", "status"])
    conn.write_message("status", '{"height":3}', ["ping", "status"])
    conn.write_message("ping", "null", ["ping", "status"])
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()
    batch = got.get("batch") or {}
    assert batch.get("ok") is True, batch
    msgs = list(batch.get("messages") or [])
    assert len(msgs) >= 2
    assert msgs[0].get("type") == "ping"
    assert any(m.get("type") == "status" for m in msgs)


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_native_read_messages_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._use_native_transport is True
    assert node._native_read_messages is True
    status = node.get_p2p_security_status()
    assert status.get("native_read_messages") is True
