#!/usr/bin/env python3
"""v1.3.125: request-bound blocks response semantic gate + prod shell fail-closed."""

from __future__ import annotations

import sys
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


def _block(height: int, parent: str, *, extra: str = "") -> dict:
    blk = Block(
        height=height,
        parent_hash=parent,
        miner="0x" + ("11" * 20),
        transactions=[],
        timestamp=1_700_000_000 + height,
        extra_data=extra,
        state_root="0" * 64,
    )
    return blk.to_dict()


def _chain(n: int = 3, start: int = 1, parent0: str = "0" * 64) -> list:
    out = []
    parent = parent0
    for h in range(start, start + n):
        b = _block(h, parent)
        out.append(b)
        parent = b["hash"]
    return out


def test_needles_v13125():
    wire = (ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs").read_text(
        encoding="utf-8"
    )
    assert "verify_blocks_response_semantics_inner" in wire
    assert "bad_blocks_response_range" in wire
    assert "bad_blocks_response_continuity" in wire
    assert "bad_blocks_response_parent" in wire
    assert "empty_blocks_response" in wire
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "verify_p2p_blocks_response_semantics" in p2p
    assert "request_ctx" in p2p
    assert "read_message_loop_events" in p2p
    assert "stale wheel is not prod-safe" in p2p
    http = (ROOT / "api" / "http.py").read_text(encoding="utf-8")
    assert "p2p_native_message_loop_shell" in http
    notes = (ROOT / "RELEASE_NOTES_v1.3.125.md").read_text(encoding="utf-8")
    assert "1.3.125-industrial" in notes
    # Live Config().node_version advances with later waves; pin notes not config.
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_blocks_response_semantic_gate" in metrics
    assert "abs_p2p_blocks_response_semantic_rejects_total" in metrics
    nat = (ROOT / "crypto" / "native.py").read_text(encoding="utf-8")
    assert "verify_p2p_blocks_response_semantics" in nat
    assert "blocks_response_native_required" in nat


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_valid_range_passes():
    chain = _chain(3, start=1, parent0="0" * 64)
    assert (
        native.verify_p2p_blocks_response_semantics(
            chain, 1, 3, "0" * 64, allow_empty=False
        )
        is None
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_wrong_first_height_rejects():
    chain = _chain(2, start=2, parent0="0" * 64)
    reason = native.verify_p2p_blocks_response_semantics(
        chain, 1, 3, "0" * 64, allow_empty=False
    )
    assert reason == "bad_blocks_response_range"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_gap_rejects():
    a = _block(1, "0" * 64)
    c = _block(3, a["hash"])  # skip height 2
    reason = native.verify_p2p_blocks_response_semantics(
        [a, c], 1, 3, "0" * 64, allow_empty=False
    )
    assert reason == "bad_blocks_response_continuity"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_bad_parent_rejects():
    a = _block(1, "0" * 64)
    b = _block(2, "ff" * 32)  # wrong parent
    reason = native.verify_p2p_blocks_response_semantics(
        [a, b], 1, 2, "0" * 64, allow_empty=False
    )
    assert reason == "bad_blocks_response_parent"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_empty_rejects_when_disallowed():
    reason = native.verify_p2p_blocks_response_semantics(
        [], 1, 2, "0" * 64, allow_empty=False
    )
    assert reason == "empty_blocks_response"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_tampered_hash_still_bad_block_hash():
    chain = _chain(1, start=1, parent0="0" * 64)
    chain[0]["extra_data"] = "tampered"
    reason = native.verify_p2p_blocks_response_semantics(
        chain, 1, 1, "0" * 64, allow_empty=False
    )
    assert reason == "bad_block_hash"


def test_prod_requires_message_loop_shell():
    cfg = Config()
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    cfg.require_native_crypto = True
    cfg.deployment_mode = "prod"
    cfg.bootstrap_peers = []
    # With a real abs_native that has the shell, construction succeeds.
    if getattr(native, "native_available", lambda: False)():
        node = P2PNode(cfg, MagicMock(), MagicMock())
        assert node._native_message_loop_shell is True
        st = node.get_p2p_security_status()
        assert st.get("native_blocks_response_semantic_gate") is True
        assert "blocks_response_semantic_rejects_total" in st
    else:
        with pytest.raises(RuntimeError):
            P2PNode(cfg, MagicMock(), MagicMock())
