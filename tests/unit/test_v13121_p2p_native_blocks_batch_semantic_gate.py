#!/usr/bin/env python3
"""v1.3.121: native blocks batch canonical-hash semantic gate on message-loop shell."""

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

from core.blockchain import Block
from crypto import native
from network.p2p_node import P2PNode
from runtime.config import Config


def _wire(msg_type: str, data) -> bytes:
    return (
        json.dumps(
            {"type": msg_type, "data": data},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _valid_block(*, height: int = 1) -> dict:
    blk = Block(
        height=height,
        parent_hash="0" * 64,
        miner="0x" + ("11" * 20),
        transactions=[],
        timestamp=1_700_000_000 + height,
        extra_data="",
        state_root="0" * 64,
    )
    return blk.to_dict()


def test_needles_v13121():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    wire = (ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs").read_text(
        encoding="utf-8"
    )
    assert "check_blocks_batch_semantics" in transport
    assert "verify_blocks_batch_semantics_inner" in wire
    assert "v1.3.121" in transport
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "test-quick" in makefile
    assert "build_native.sh" in makefile
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_blocks_batch_semantic_gate" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.121.md").read_text(encoding="utf-8")
    assert "1.3.121-industrial" in notes
    assert Config().node_version == "1.3.121-industrial"
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_blocks_batch_semantic_gate" in metrics


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
                    8, 65536, ["blocks", "status"], False, None, False
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
def test_native_loop_dispatches_valid_blocks_batch():
    batch = [_valid_block(height=1), _valid_block(height=2)]
    out = _loop_once(_wire("blocks", batch))
    assert out.get("ok") is True
    events = list(out.get("events") or [])
    assert any(e.get("action") == "dispatch" and e.get("type") == "blocks" for e in events)


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_strikes_tampered_batch_block():
    good = _valid_block(height=1)
    bad = _valid_block(height=2)
    bad["extra_data"] = "tampered"
    out = _loop_once(_wire("blocks", [good, bad]))
    events = list(out.get("events") or [])
    assert any(
        e.get("action") == "strike" and e.get("reason") == "bad_block_hash"
        for e in events
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_loop_empty_batch_ok():
    out = _loop_once(_wire("blocks", []))
    events = list(out.get("events") or [])
    assert any(e.get("action") == "dispatch" and e.get("type") == "blocks" for e in events)


def test_status_exposes_blocks_batch_semantic_gate():
    cfg = Config()
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    node = P2PNode(cfg, MagicMock(), MagicMock())
    node._native_message_loop_shell = True
    st = node.get_p2p_security_status()
    assert st.get("native_blocks_batch_semantic_gate") is True
