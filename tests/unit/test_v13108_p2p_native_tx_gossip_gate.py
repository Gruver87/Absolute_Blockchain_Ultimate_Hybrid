#!/usr/bin/env python3
"""v1.3.108: native new_tx / mempool shape gates on read path."""

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

ALLOWED = ["new_tx", "mempool"]


def test_needles_v13108():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "check_wire_tx_payload" in transport
    assert "check_mempool_batch_payload" in transport
    assert "check_ingress_shape_gates" in transport
    assert "v1.3.108" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_tx_gossip_gate" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.108.md").read_text(encoding="utf-8")
    assert "1.3.108-industrial" in notes
    assert Config().node_version == "1.3.108-industrial"
    assert "abs_p2p_native_tx_gossip_gate" in (
        ROOT / "observability" / "metrics.py"
    ).read_text(encoding="utf-8")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_rejects_bad_wire_tx():
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
    conn.write_message("new_tx", "{}", ALLOWED)
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()

    batch = got.get("batch") or {}
    assert batch.get("ok") is False, batch
    assert batch.get("reason") == "bad_wire_tx"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_rejects_bad_mempool_batch():
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
    conn.write_message("mempool", '{"transactions": [{}]}', ALLOWED)
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()

    msg = got.get("msg") or {}
    assert msg.get("ok") is False, msg
    assert msg.get("reason") == "bad_mempool_batch"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_allows_well_shaped_new_tx():
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
    conn.write_message("new_tx", '{"from":"alice","to":"bob"}', ALLOWED)
    time.sleep(0.15)
    conn.close()
    t.join(timeout=3)
    listener.close()
    msg = got.get("msg") or {}
    assert msg.get("ok") is True, msg
    assert msg.get("type") == "new_tx"


def test_p2p_node_native_tx_gossip_gate_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node.get_p2p_security_status().get("native_tx_gossip_gate") is True
