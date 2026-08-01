#!/usr/bin/env python3
"""Unit tests for tip-safety AncestryWindow (ADR 0016 stage-1.5)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from consensus.tip_safety import AncestryWindow, ApplyOutcome, ReorgPolicy, TipSafetyService
from consensus.tip_safety.errors import TipUnknownParentError
from consensus.tip_safety.tip_state import TipState
from consensus.tip_safety.types import BlockRef


def _h(n: int) -> str:
    return f"{n:064x}"


def _b(height: int, *, h: int | None = None, parent: str | None = None) -> BlockRef:
    digest = _h(h if h is not None else height)
    if height == 0:
        return BlockRef(height=0, block_hash=digest, parent_hash="")
    return BlockRef(
        height=height,
        block_hash=digest,
        parent_hash=parent if parent is not None else _h(height - 1),
    )


def test_ancestry_window_lru_evicts() -> None:
    w = AncestryWindow(max_blocks=3)
    for i in range(5):
        w.record(_b(i))
    assert len(w) == 3
    assert w.get(_h(0)) is None
    assert w.get(_h(4)) is not None


def test_window_rollback_to_recorded_ancestor() -> None:
    svc = TipSafetyService(TipState(head=_b(0)), ancestry_max_blocks=64)
    for h in range(1, 6):
        d = svc.apply_candidate(_b(h))
        assert d.accepted, d.detail
    assert svc.state.snapshot().head.height == 5
    decision = svc.evaluate_candidate(_b(2))
    assert decision.outcome == ApplyOutcome.ACCEPT_REORG
    applied = svc.apply_candidate(_b(2))
    assert applied.accepted
    assert svc.state.snapshot().head.height == 2


def test_deep_reorg_still_rejected_without_recorded_chain() -> None:
    state = TipState(head=_b(10), finalized=_b(2))
    with pytest.raises(TipUnknownParentError):
        ReorgPolicy().evaluate(state, _b(5))
