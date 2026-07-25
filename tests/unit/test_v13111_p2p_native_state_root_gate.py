#!/usr/bin/env python3
"""v1.3.111: native state_root_request / state_root_response shape gates."""

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

ALLOWED = ["state_root_request", "state_root_response"]


def test_needles_v13111():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "check_state_root_request_payload" in transport
    assert "check_state_root_response_payload" in transport
    assert "v1.3.111" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_state_root_gate" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.111.md").read_text(encoding="utf-8")
    assert "1.3.111-industrial" in notes
    assert Config().node_version == "1.3.111-industrial"
    assert "abs_p2p_native_state_root_gate" in (
        ROOT / "observability" / "metrics.py"
    ).read_text(encoding="utf-8")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_rejects_bad_state_root_request():
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
                batch = c.read_messages(8, 65536, ALLOWED, False)
                got["batch"] = batch
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write_message("state_root_request", '{"height": -1}', ALLOWED)
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()

    batch = got.get("batch") or {}
    assert batch.get("ok") is False, batch
    assert batch.get("reason") == "bad_state_root_request"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_rejects_bad_state_root_response():
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
                msg = c.read_message(65536, ALLOWED, False)
                got["msg"] = msg
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write_message("state_root_response", "null", ALLOWED)
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()

    msg = got.get("msg") or {}
    assert msg.get("ok") is False, msg
    assert msg.get("reason") == "bad_state_root_response"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_allows_well_shaped_state_root_request():
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
                msg = c.read_message(65536, ALLOWED, False)
                got["msg"] = msg
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write_message("state_root_request", '{"height": 3}', ALLOWED)
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()
    msg = got.get("msg") or {}
    assert msg.get("ok") is True, msg
    assert msg.get("type") == "state_root_request"


def test_p2p_node_native_state_root_gate_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node.get_p2p_security_status().get("native_state_root_gate") is True
