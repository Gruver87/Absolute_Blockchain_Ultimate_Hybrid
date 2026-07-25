#!/usr/bin/env python3
"""v1.3.123: native state_root_response digest semantic gate on message-loop shell."""

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
DIGEST2 = "cd" * 32


def _wire(msg_type: str, data) -> bytes:
    return (
        json.dumps(
            {"type": msg_type, "data": data},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _ok_payload() -> dict:
    return {"height": 3, "state_root": DIGEST, "head_hash": DIGEST2}


def test_needles_v13123():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    wire = (ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs").read_text(
        encoding="utf-8"
    )
    assert "check_state_root_response_semantics" in transport
    assert "verify_state_root_response_semantics_inner" in wire
    assert "bad_state_root_digest" in wire
    assert "v1.3.123" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_state_root_response_semantic_gate" in p2p
    assert "state_root_semantic_rejects_total" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.123.md").read_text(encoding="utf-8")
    assert "1.3.123-industrial" in notes
    assert Config().node_version == "1.3.123-industrial"
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_state_root_response_semantic_gate" in metrics
    assert "abs_p2p_state_root_semantic_rejects_total" in metrics


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
                    8,
                    65536,
                    ["state_root_response", "status"],
                    False,
                    None,
                    False,
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
def test_native_loop_dispatches_valid_digests():
    out = _loop_once(_wire("state_root_response", _ok_payload()))
    assert out.get("ok") is True
    events = list(out.get("events") or [])
    assert any(
        e.get("action") == "dispatch" and e.get("type") == "state_root_response"
        for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_strikes_non_hex_root():
    bad = _ok_payload()
    bad["state_root"] = "zz" * 32
    out = _loop_once(_wire("state_root_response", bad))
    events = list(out.get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_state_root_digest"
        for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_strikes_wrong_length():
    bad = _ok_payload()
    bad["state_root"] = "ab" * 16  # 32 hex = 16 bytes
    out = _loop_once(_wire("state_root_response", bad))
    events = list(out.get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_state_root_digest"
        for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_strikes_bad_head_hash():
    bad = _ok_payload()
    bad["head_hash"] = "not-a-digest"
    out = _loop_once(_wire("state_root_response", bad))
    events = list(out.get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_state_root_digest"
        for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_shape_still_strikes_null():
    out = _loop_once(_wire("state_root_response", None))
    events = list(out.get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_state_root_response"
        for e in events
    )


def test_status_exposes_state_root_response_semantic_gate():
    cfg = Config()
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    node = P2PNode(cfg, MagicMock(), MagicMock())
    node._native_message_loop_shell = True
    st = node.get_p2p_security_status()
    assert st.get("native_state_root_response_semantic_gate") is True
    assert "state_root_semantic_rejects_total" in st
