#!/usr/bin/env python3
"""v1.3.126: request-bound singular block response semantic gate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.blockchain import Block
from crypto import native
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


def test_needles_v13126():
    wire = (ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs").read_text(
        encoding="utf-8"
    )
    assert "verify_block_response_semantics_inner" in wire
    assert "bad_block_response_hash" in wire
    assert "empty_block_response" in wire
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "verify_p2p_block_response_semantics" in p2p
    assert 'kind": "block"' in p2p or "kind': 'block'" in p2p or '"kind": "block"' in p2p
    assert "expected_hash" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.126.md").read_text(encoding="utf-8")
    assert "1.3.126-industrial" in notes
    assert Config().node_version == "1.3.126-industrial"
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_block_response_semantic_gate" in metrics
    assert "abs_p2p_block_response_semantic_rejects_total" in metrics
    nat = (ROOT / "crypto" / "native.py").read_text(encoding="utf-8")
    assert "verify_p2p_block_response_semantics" in nat
    assert "block_response_native_required" in nat


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_matching_hash_passes():
    b = _block(1, "0" * 64)
    assert (
        native.verify_p2p_block_response_semantics(b, b["hash"], allow_null=True)
        is None
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_null_ok_when_allowed():
    assert (
        native.verify_p2p_block_response_semantics(None, "aa" * 32, allow_null=True)
        is None
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_null_rejects_when_disallowed():
    reason = native.verify_p2p_block_response_semantics(
        None, "aa" * 32, allow_null=False
    )
    assert reason == "empty_block_response"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_wrong_hash_rejects():
    b = _block(1, "0" * 64)
    other = _block(2, b["hash"])
    reason = native.verify_p2p_block_response_semantics(
        other, b["hash"], allow_null=True
    )
    assert reason == "bad_block_response_hash"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_tampered_hash_still_bad_block_hash():
    b = _block(1, "0" * 64)
    wanted = b["hash"]
    b["extra_data"] = "tampered"
    reason = native.verify_p2p_block_response_semantics(b, wanted, allow_null=True)
    assert reason == "bad_block_hash"
