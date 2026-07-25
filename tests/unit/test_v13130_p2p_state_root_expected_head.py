#!/usr/bin/env python3
"""v1.3.130: soft expected_head on state_root waiters + professional repo needles."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native


DIGEST = "aa" * 32
OTHER = "bb" * 32


def _resp(height: int, head: str = DIGEST) -> dict:
    return {
        "height": height,
        "state_root": "cc" * 32,
        "head_hash": head,
    }


def test_needles_v13130():
    assert (ROOT / ".github" / "dependabot.yml").is_file()
    assert (ROOT / ".editorconfig").is_file()
    assert (ROOT / "SUPPORT.md").is_file()
    assert (ROOT / "docs" / "AUDITS.md").is_file()
    assert (ROOT / "docs" / "RELEASING.md").is_file()
    assert (ROOT / "docs" / "REPO_PROFESSIONAL.md").is_file()
    assert (ROOT / ".github" / "workflows" / "sbom-on-release.yml").is_file()
    wire = (ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs").read_text(
        encoding="utf-8"
    )
    assert "bad_state_root_response_head" in wire
    assert "expected_head" in wire
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "expected_head" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.130.md").read_text(encoding="utf-8")
    assert "1.3.130-industrial" in notes
    # Live Config().node_version advances with later waves; pin notes not config.
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_state_root_response_head_gate" in metrics


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_matching_head_passes():
    assert (
        native.verify_p2p_state_root_response_request_semantics(
            _resp(7), 7, DIGEST
        )
        is None
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_empty_expected_head_skips():
    assert (
        native.verify_p2p_state_root_response_request_semantics(_resp(7, OTHER), 7, "")
        is None
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_wrong_head_rejects():
    reason = native.verify_p2p_state_root_response_request_semantics(
        _resp(7, OTHER), 7, DIGEST
    )
    assert reason == "bad_state_root_response_head"
