#!/usr/bin/env python3
"""v1.3.99: native keepalive — consume inbound pong + empty-batch touch."""

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

from crypto import native
from network.p2p_node import P2PNode
from runtime.config import Config


def test_needles_v1399():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "keepalive_touches" in transport
    assert "auto_keeps" in transport
    assert "v1.3.99" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "keepalive_touches" in p2p
    assert "native_keepalive" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.99.md").read_text(encoding="utf-8")
    assert "1.3.99-industrial" in notes
    assert Config().node_version == "1.3.99-industrial"
    assert "abs_p2p_native_keepalive" in (
        ROOT / "observability" / "metrics.py"
    ).read_text(encoding="utf-8")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_consume_inbound_pong():
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
                # pong consumed; status returned
                batch = c.read_messages(8, 65536, ["ping", "pong", "status"], True)
                got["batch"] = batch
                got["auto_keeps"] = int(c.auto_keeps or 0)
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write_message("pong", '{"ts":1.0}', ["ping", "pong", "status"])
    conn.write_message("status", '{"height":1}', ["ping", "pong", "status"])
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()

    batch = got.get("batch") or {}
    assert batch.get("ok") is True, batch
    assert int(batch.get("keepalive_touches") or 0) >= 1
    msgs = list(batch.get("messages") or [])
    assert any(m.get("type") == "status" for m in msgs)
    assert not any(m.get("type") == "pong" for m in msgs)
    assert int(got.get("auto_keeps") or 0) >= 1


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_native_keepalive_status():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_native_auto_pong = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    st = node.get_p2p_security_status()
    assert st.get("native_auto_pong") is True
    assert st.get("native_keepalive") is True
