#!/usr/bin/env python3
"""v1.3.101: configurable native batch/chunk sizes."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native
from network.p2p_node import P2PNode, _clamp_native_batch, _clamp_native_chunk
from runtime.config import Config


def test_needles_v13101():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "p2p_native_clamp_batch" in transport
    assert "NATIVE_BATCH_MAX" in transport
    assert "v1.3.101" in transport
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_native_read_batch" in cfg
    assert "p2p_native_write_batch" in cfg
    assert "p2p_native_read_chunk" in cfg
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "_clamp_native_batch" in p2p
    assert "native_read_batch" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.101.md").read_text(encoding="utf-8")
    assert "1.3.101-industrial" in notes
    assert Config().node_version == "1.3.101-industrial"
    assert "abs_p2p_native_read_batch" in (
        ROOT / "observability" / "metrics.py"
    ).read_text(encoding="utf-8")


def test_clamp_helpers_python_fallback():
    assert _clamp_native_batch(100) == 64
    assert _clamp_native_batch(16) == 16
    assert _clamp_native_batch(0) in (1, 8)  # native clamp→1; pure-py fallback→default 8
    assert _clamp_native_chunk(100) == 1024
    assert _clamp_native_chunk(2_000_000) == 1024 * 1024
    assert _clamp_native_chunk(8192) == 8192


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_clamp_exports():
    assert native.p2p_native_clamp_batch(0) == 1
    assert native.p2p_native_clamp_batch(99) == 64
    assert native.p2p_native_clamp_chunk(10) == 1024
    assert native.p2p_native_clamp_chunk(9_000_000) == 1024 * 1024


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_applies_batch_config():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    cfg.p2p_native_read_batch = 32
    cfg.p2p_native_write_batch = 4
    cfg.p2p_native_read_chunk = 8192
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._native_read_batch == 32
    assert node._native_write_batch == 4
    assert node._native_read_chunk == 8192
    st = node.get_p2p_security_status()
    assert st.get("native_read_batch") == 32
    assert st.get("native_write_batch") == 4
    assert st.get("native_read_chunk") == 8192
