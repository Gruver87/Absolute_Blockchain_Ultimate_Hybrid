#!/usr/bin/env python3
"""v1.3.127: request-bound state_root_response height semantic gate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native
from runtime.config import Config


def _resp(height: int) -> dict:
    return {
        "height": height,
        "state_root": "aa" * 32,
        "head_hash": "bb" * 32,
    }


def test_needles_v13127():
    wire = (ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs").read_text(
        encoding="utf-8"
    )
    assert "verify_state_root_response_request_semantics_inner" in wire
    assert "bad_state_root_response_height" in wire
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "verify_p2p_state_root_response_request_semantics" in p2p
    assert '"kind": "state_root"' in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.127.md").read_text(encoding="utf-8")
    assert "1.3.127-industrial" in notes
    assert Config().node_version == "1.3.127-industrial"
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_state_root_response_request_gate" in metrics
    assert "abs_p2p_state_root_response_request_rejects_total" in metrics
    nat = (ROOT / "crypto" / "native.py").read_text(encoding="utf-8")
    assert "verify_p2p_state_root_response_request_semantics" in nat
    assert "state_root_response_request_native_required" in nat


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_matching_height_passes():
    assert (
        native.verify_p2p_state_root_response_request_semantics(_resp(7), 7) is None
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_wrong_height_rejects():
    reason = native.verify_p2p_state_root_response_request_semantics(_resp(7), 8)
    assert reason == "bad_state_root_response_height"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_bad_digest_still_rejects():
    bad = {"height": 1, "state_root": "zz", "head_hash": "bb" * 32}
    reason = native.verify_p2p_state_root_response_request_semantics(bad, 1)
    assert reason in ("bad_state_root_digest", "bad_state_root_response")
