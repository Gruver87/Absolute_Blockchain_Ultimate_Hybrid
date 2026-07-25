#!/usr/bin/env python3
"""v1.3.95: native batch write_messages / write_payloads pumps."""

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


def test_needles_v1395():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "write_messages" in transport
    assert "write_payloads" in transport
    assert "v1.3.95" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_write_messages_batch" in p2p
    assert "_native_write_messages" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "1.3.95-industrial" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.95.md").read_text(encoding="utf-8")
    assert "1.3.95-industrial" in notes
    assert Config().node_version == "1.3.95-industrial"
    assert hasattr(abs_native.P2PNativeConn, "write_messages")
    assert hasattr(abs_native.P2PNativeConn, "write_payloads")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_write_messages_batch():
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
    out = conn.write_messages(
        [("ping", "null"), ("status", '{"height":9}'), ("ping", "null")],
        ["ping", "status"],
    )
    assert out.get("ok") is True, out
    assert int(out.get("count") or 0) == 3
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()
    batch = got.get("batch") or {}
    assert batch.get("ok") is True, batch
    msgs = list(batch.get("messages") or [])
    assert len(msgs) >= 2
    assert msgs[0].get("type") == "ping"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_write_payloads_batch():
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
                got["batch"] = c.read_messages(4, 65536, ["ping"])
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    payloads = [
        b'{"type":"ping","data":null}\n',
        b'{"type":"ping","data":{"n":1}}\n',
    ]
    out = conn.write_payloads(payloads)
    assert out.get("ok") is True, out
    assert int(out.get("count") or 0) == 2
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()
    assert (got.get("batch") or {}).get("ok") is True


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_native_write_messages_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._native_write_messages is True
    assert node.get_p2p_security_status().get("native_write_messages") is True
