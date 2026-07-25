#!/usr/bin/env python3
"""v1.3.117: native attestation semantic gate on message-loop shell."""

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
from crypto.validator_keys import ValidatorKeys
from network.p2p_node import P2PNode
from runtime.config import Config


def _wire(msg_type: str, data: dict) -> bytes:
    return (
        json.dumps(
            {"type": msg_type, "data": data},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _signed_attestation() -> dict:
    keys = ValidatorKeys().initialize()
    return keys.sign_attestation({"hash": "aa" * 16, "number": 1}, slot=7)


def test_needles_v13117():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "check_attestation_semantics" in transport
    assert "verify_attestation_semantics_inner" in (
        ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs"
    ).read_text(encoding="utf-8")
    assert "bad_attestation_identity" in transport or "bad_attestation_identity" in (
        ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs"
    ).read_text(encoding="utf-8")
    assert "v1.3.117" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_attestation_semantic_gate" in p2p
    assert "attestation_semantic_rejects_total" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.117.md").read_text(encoding="utf-8")
    assert "1.3.117-industrial" in notes
    # Live Config().node_version advances with later waves; pin notes not config.
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_attestation_semantic_gate" in metrics
    assert "abs_p2p_attestation_semantic_rejects_total" in metrics


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_dispatches_valid_attestation():
    att = _signed_attestation()
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
                    8, 65536, ["attestation", "status"], False
                )
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write(_wire("attestation", att))
    conn.close()
    t.join(timeout=5)
    assert got.get("out", {}).get("ok") is True
    events = list(got["out"].get("events") or [])
    assert any(
        e.get("action") == "dispatch" and e.get("type") == "attestation" for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_strikes_bad_attestation_sig():
    att = _signed_attestation()
    # Tamper target_hash while keeping shape + signature bytes
    att["target_hash"] = "bb" * 16
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
                    8, 65536, ["attestation"], False
                )
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write(_wire("attestation", att))
    conn.close()
    t.join(timeout=5)
    events = list(got.get("out", {}).get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_attestation_sig"
        for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_strikes_bad_attestation_identity():
    att = _signed_attestation()
    att["validator"] = "0x" + ("11" * 20)
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
                    8, 65536, ["attestation"], False
                )
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(host, port, 1024 * 1024, 8000)
    conn.write(_wire("attestation", att))
    conn.close()
    t.join(timeout=5)
    events = list(got.get("out", {}).get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_attestation_identity"
        for e in events
    )


def test_status_exposes_attestation_semantic_gate():
    cfg = Config()
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    node = P2PNode(cfg, MagicMock(), MagicMock())
    # Force shell flag for status even if transport init differs in unit env
    node._native_message_loop_shell = True
    st = node.get_p2p_security_status()
    assert st.get("native_attestation_semantic_gate") is True
    assert "attestation_semantic_rejects_total" in st
