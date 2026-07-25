#!/usr/bin/env python3
"""v1.3.102: configurable native socket I/O timeout."""

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
from network.p2p_node import P2PNode, _clamp_native_timeout_ms
from runtime.config import Config


def test_needles_v13102():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "p2p_native_clamp_timeout_ms" in transport
    assert "NATIVE_IO_TIMEOUT_DEFAULT_MS" in transport
    assert "v1.3.102" in transport
    assert "io_timeout_ms" in transport
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_native_io_timeout_ms" in cfg
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_apply_native_io_timeout" in p2p
    assert "_native_recv_wait_sec" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.102.md").read_text(encoding="utf-8")
    assert "1.3.102-industrial" in notes
    assert Config().node_version == "1.3.102-industrial"
    assert "abs_p2p_native_io_timeout_ms" in (
        ROOT / "observability" / "metrics.py"
    ).read_text(encoding="utf-8")


def test_clamp_timeout_helpers():
    assert _clamp_native_timeout_ms(100) == 1000
    assert _clamp_native_timeout_ms(900_000) == 600_000
    assert _clamp_native_timeout_ms(15_000) == 15_000


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_clamp_timeout_export():
    assert native.p2p_native_clamp_timeout_ms(50) == 1000
    assert native.p2p_native_clamp_timeout_ms(999_999) == 600_000


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_set_timeout_ms_roundtrip():
    listener = native.P2PNativeListener("127.0.0.1", 0, 1024 * 1024, 500)
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
                c.set_timeout_ms(12_000)
                got["ms"] = int(c.io_timeout_ms or 0)
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write_message("status", '{"height":1}', ["status"])
    time.sleep(0.1)
    conn.close()
    t.join(timeout=3)
    listener.close()
    assert int(got.get("ms") or 0) == 12_000


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_io_timeout_config():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    cfg.p2p_native_io_timeout_ms = 45_000
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._native_io_timeout_ms == 45_000
    assert node.get_p2p_security_status().get("native_io_timeout_ms") == 45_000
