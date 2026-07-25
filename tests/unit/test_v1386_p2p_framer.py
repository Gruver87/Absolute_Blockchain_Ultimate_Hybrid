#!/usr/bin/env python3
"""v1.3.86: native NDJSON P2P line framer (fail-closed before newline)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import abs_native

from crypto import native
from network.p2p_node import P2PNode
from runtime.config import Config
from unittest.mock import MagicMock


def test_needles_v1386():
    frame = (ROOT / "native" / "abs_native" / "src" / "p2p_frame.rs").read_text(
        encoding="utf-8"
    )
    assert "P2PLineFramer" in frame
    assert "p2p_line_too_large" in frame
    assert "v1.3.86" in frame
    lib = (ROOT / "native" / "abs_native" / "src" / "lib.rs").read_text(encoding="utf-8")
    assert "mod p2p_frame" in lib
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_read_wire_line" in p2p
    assert "P2PLineFramer" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "1.3.86-industrial" in cfg
    assert hasattr(abs_native, "P2PLineFramer")
    assert hasattr(native, "P2PLineFramer")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_framer_splits_multiple_lines():
    framer = native.P2PLineFramer(2 * 1024 * 1024)
    out = framer.feed(b'{"type":"ping","data":null}\n{"type":"pong","data":{}}\n')
    assert out["ok"] is True
    lines = list(out["lines"])
    assert len(lines) == 2
    assert lines[0].endswith(b"\n")
    assert b"ping" in lines[0]
    assert b"pong" in lines[1]
    assert int(framer.pending_len) == 0


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_framer_buffers_partial_then_completes():
    framer = native.P2PLineFramer(2 * 1024 * 1024)
    a = framer.feed(b'{"type":"ping"')
    assert a["ok"] is True
    assert list(a["lines"]) == []
    assert int(framer.pending_len) > 0
    b = framer.feed(b',"data":null}\n')
    assert b["ok"] is True
    lines = list(b["lines"])
    assert len(lines) == 1
    assert b"ping" in lines[0]


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_framer_rejects_oversize_before_newline():
    # clamp_max_bytes enforces minimum 4096
    framer = native.P2PLineFramer(100)
    assert int(framer.max_bytes) >= 4096
    limit = int(framer.max_bytes)
    blob = b"x" * (limit + 1)
    out = framer.feed(blob)
    assert out["ok"] is False
    assert out["reason"] == "p2p_line_too_large"
    assert int(framer.oversize_rejects) >= 1
    assert framer.skipping is True
    # Resync on newline then accept a real frame
    sync = framer.feed(b"\n" + b'{"type":"ping","data":null}\n')
    assert sync["ok"] is True
    lines = list(sync["lines"])
    assert len(lines) == 1
    assert b"ping" in lines[0]
    assert framer.skipping is False


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_exposes_framer_status():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    node = P2PNode(cfg, MagicMock(), MagicMock())
    status = node.get_p2p_security_status()
    assert status.get("native_p2p_framer") is True
