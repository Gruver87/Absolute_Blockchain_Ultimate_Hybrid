#!/usr/bin/env python3
"""Unit tests for catch-up policy / orchestrator (ADR 0003)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sync.catchup import CatchUpOrchestrator, CatchUpPolicy


def test_ahead_no_head_refuse() -> None:
    p = CatchUpPolicy()
    assert (
        p.ahead_refuse_reason(
            local_height=1, peer_height=5, peer_head="", require_head=True
        )
        == "catch_up_no_head"
    )


def test_height_continuity() -> None:
    orch = CatchUpOrchestrator()
    assert (
        orch.height_continuity_refuse_reason({"height": 3}, 3) == ""
    )
    assert (
        orch.height_continuity_refuse_reason({"height": 4}, 3)
        == "catch_up_height_continuity_mismatch"
    )


def test_tip_head_at_height() -> None:
    orch = CatchUpOrchestrator()
    assert (
        orch.tip_head_at_height_refuse_reason(
            local_height=5,
            peer_height=5,
            local_head="aa" * 32,
            peer_head="bb" * 32,
        )
        == "catch_up_tip_head_mismatch"
    )
    assert (
        orch.tip_head_at_height_refuse_reason(
            local_height=4,
            peer_height=5,
            local_head="aa" * 32,
            peer_head="bb" * 32,
        )
        == ""
    )


def test_no_p2p_import_in_sync_catchup() -> None:
    for rel in (
        "sync/catchup/orchestrator.py",
        "sync/catchup/policy.py",
        "sync/ports.py",
        "sync/consistency/machine.py",
        "sync/solicit.py",
    ):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "from network" not in src
        assert "import network" not in src
