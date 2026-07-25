#!/usr/bin/env python3
"""v1.3.124: native status.head_hash digest semantic gate on message-loop shell."""

from __future__ import annotations

import json
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

DIGEST = "ab" * 32


def _wire(msg_type: str, data) -> bytes:
    return (
        json.dumps(
            {"type": msg_type, "data": data},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def test_needles_v13124():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    wire = (ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs").read_text(
        encoding="utf-8"
    )
    assert "check_status_head_hash_semantics" in transport
    assert "verify_status_head_hash_semantics_inner" in wire
    assert "bad_status_head_digest" in wire
    assert "v1.3.124" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_status_head_hash_semantic_gate" in p2p
    assert "status_semantic_rejects_total" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.124.md").read_text(encoding="utf-8")
    assert "1.3.124-industrial" in notes
    # Live Config().node_version advances with later waves; pin notes not config.
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_status_head_hash_semantic_gate" in metrics
    assert "abs_p2p_status_semantic_rejects_total" in metrics


def _loop_once(payload: bytes) -> dict:
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
                got["out"] = c.read_message_loop_events(
                    8, 65536, ["status", "ping"], False, None, False
                )
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write(payload)
    conn.close()
    t.join(timeout=5)
    return got.get("out") or {}


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_dispatches_valid_head_hash():
    out = _loop_once(_wire("status", {"height": 1, "head_hash": DIGEST}))
    assert out.get("ok") is True
    events = list(out.get("events") or [])
    assert any(e.get("action") == "dispatch" and e.get("type") == "status" for e in events)


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_dispatches_0x_prefixed():
    out = _loop_once(_wire("status", {"height": 1, "head_hash": "0x" + DIGEST}))
    events = list(out.get("events") or [])
    assert any(e.get("action") == "dispatch" and e.get("type") == "status" for e in events)


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_strikes_non_hex():
    out = _loop_once(_wire("status", {"height": 1, "head_hash": "zz" * 32}))
    events = list(out.get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_status_head_digest"
        for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_strikes_wrong_length():
    out = _loop_once(_wire("status", {"height": 1, "head_hash": "ab" * 16}))
    events = list(out.get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_status_head_digest"
        for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_empty_and_null_ok():
    for data in (None, {}, {"height": 0, "head_hash": ""}):
        out = _loop_once(_wire("status", data))
        events = list(out.get("events") or [])
        assert any(
            e.get("action") == "dispatch" and e.get("type") == "status" for e in events
        ), data


def test_status_exposes_status_head_hash_semantic_gate():
    cfg = Config()
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    node = P2PNode(cfg, MagicMock(), MagicMock())
    node._native_message_loop_shell = True
    st = node.get_p2p_security_status()
    assert st.get("native_status_head_hash_semantic_gate") is True
    assert "status_semantic_rejects_total" in st
