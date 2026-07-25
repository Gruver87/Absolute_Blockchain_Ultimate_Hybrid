#!/usr/bin/env python3
"""v1.3.104: native status payload gate on read path."""

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


def test_needles_v13104():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "check_status_payload" in transport
    assert "validate_status_inner" in transport
    assert "v1.3.104" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_status_gate" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.104.md").read_text(encoding="utf-8")
    assert "1.3.104-industrial" in notes
    assert Config().node_version == "1.3.104-industrial"
    assert "abs_p2p_native_status_gate" in (
        ROOT / "observability" / "metrics.py"
    ).read_text(encoding="utf-8")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_rejects_bad_status_payload():
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
                batch = c.read_messages(8, 65536, ["status", "ping"], False)
                got["batch"] = batch
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    # Negative height fails validate_status_inner
    conn.write_message("status", '{"height":-1,"head_hash":"x"}', ["status", "ping"])
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()

    batch = got.get("batch") or {}
    assert batch.get("ok") is False, batch
    assert batch.get("reason") == "bad_status_payload"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_allows_null_status():
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
                msg = c.read_message(65536, ["status", "ping"], False)
                got["msg"] = msg
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write(b'{"type":"status","data":null}\n')
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()
    msg = got.get("msg") or {}
    assert msg.get("ok") is True, msg
    assert msg.get("type") == "status"


def test_p2p_node_native_status_gate_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node.get_p2p_security_status().get("native_status_gate") is True
