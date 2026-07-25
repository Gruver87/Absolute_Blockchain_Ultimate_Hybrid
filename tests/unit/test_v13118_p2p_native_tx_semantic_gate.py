#!/usr/bin/env python3
"""v1.3.118: native new_tx signature semantic gate on message-loop shell."""

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
from crypto.wallet import Wallet
from network.p2p_node import P2PNode
from runtime.config import Config

CHAIN = 778888


def _wire(msg_type: str, data: dict) -> bytes:
    return (
        json.dumps(
            {"type": msg_type, "data": data},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _signed_tx(*, chain_id: int = CHAIN, to: str = "0x" + ("22" * 20)) -> dict:
    w = Wallet.create_new()
    return w.sign_transaction(to=to, value=1, nonce=0, chain_id=chain_id)


def test_needles_v13118():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    wire = (ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs").read_text(
        encoding="utf-8"
    )
    assert "check_wire_tx_semantics" in transport
    assert "verify_wire_tx_signature_inner" in wire
    assert "missing_tx_signature" in wire
    assert "v1.3.118" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_tx_semantic_gate" in p2p
    assert "tx_semantic_rejects_total" in p2p
    assert "require_tx_signatures" in p2p or "require_signatures" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.118.md").read_text(encoding="utf-8")
    assert "1.3.118-industrial" in notes
    assert Config().node_version == "1.3.118-industrial"
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_tx_semantic_gate" in metrics
    assert "abs_p2p_tx_semantic_rejects_total" in metrics


def _loop_once(payload: bytes, *, chain_id: int, require_sigs: bool) -> dict:
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
                    8, 65536, ["new_tx", "status"], False, chain_id, require_sigs
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
def test_native_loop_dispatches_valid_signed_tx():
    tx = _signed_tx()
    out = _loop_once(_wire("new_tx", tx), chain_id=CHAIN, require_sigs=True)
    assert out.get("ok") is True
    events = list(out.get("events") or [])
    assert any(e.get("action") == "dispatch" and e.get("type") == "new_tx" for e in events)


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_strikes_tampered_tx():
    tx = _signed_tx()
    tx["value"] = 999999
    out = _loop_once(_wire("new_tx", tx), chain_id=CHAIN, require_sigs=True)
    events = list(out.get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_tx_signature"
        for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_strikes_wrong_chain_preimage():
    # Signed for chain 1, verified under expected 778888 → bad_tx_signature
    tx = _signed_tx(chain_id=1)
    out = _loop_once(_wire("new_tx", tx), chain_id=CHAIN, require_sigs=True)
    events = list(out.get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_tx_signature"
        for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_missing_sig_policy():
    tx = {
        "from": "0x" + ("11" * 20),
        "to": "0x" + ("22" * 20),
        "value": 1,
        "nonce": 0,
    }
    out_req = _loop_once(_wire("new_tx", tx), chain_id=CHAIN, require_sigs=True)
    assert any(
        e.get("action") == "strike" and e.get("reason") == "missing_tx_signature"
        for e in (out_req.get("events") or [])
    )
    out_opt = _loop_once(_wire("new_tx", tx), chain_id=CHAIN, require_sigs=False)
    assert any(
        e.get("action") == "dispatch" and e.get("type") == "new_tx"
        for e in (out_opt.get("events") or [])
    )


def test_status_exposes_tx_semantic_gate():
    cfg = Config()
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    node = P2PNode(cfg, MagicMock(), MagicMock())
    node._native_message_loop_shell = True
    st = node.get_p2p_security_status()
    assert st.get("native_tx_semantic_gate") is True
    assert "tx_semantic_rejects_total" in st
