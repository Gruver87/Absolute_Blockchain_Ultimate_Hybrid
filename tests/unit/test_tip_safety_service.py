#!/usr/bin/env python3
"""Unit tests for TipSafetyService — apply, reject, finality."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from consensus.tip_safety.errors import TipFinalityRegressError, TipValidationError
from consensus.tip_safety.service import TipSafetyService
from consensus.tip_safety.tip_state import TipState
from consensus.tip_safety.types import ApplyOutcome, BlockRef


def _h(n: int) -> str:
    return f"{n:064x}"


def _b(height: int, *, n: int | None = None) -> BlockRef:
    digest = _h(n if n is not None else height)
    if height == 0:
        return BlockRef(height=0, block_hash=digest, parent_hash="")
    return BlockRef(height=height, block_hash=digest, parent_hash=_h(height - 1))


def test_apply_extend_updates_state() -> None:
    svc = TipSafetyService(TipState(head=_b(1)))
    cand = BlockRef(height=2, block_hash=_h(2), parent_hash=_h(1))
    decision = svc.apply_candidate(cand)
    assert decision.outcome == ApplyOutcome.ACCEPT_EXTEND
    assert svc.state.head.height == 2


def test_evaluate_reject_does_not_mutate() -> None:
    svc = TipSafetyService(TipState(head=_b(1)))
    decision = svc.evaluate_candidate(_b(1))
    assert decision.outcome == ApplyOutcome.REJECT
    assert decision.reason_code == "tip_duplicate"
    assert svc.state.head.height == 1


def test_choose_and_apply_picks_higher() -> None:
    svc = TipSafetyService(TipState(head=_b(1)))
    c2 = BlockRef(height=2, block_hash=_h(2), parent_hash=_h(1))
    # Rival at height 2 with higher hash — still needs parent=tip
    c2b = BlockRef(height=2, block_hash=_h(20), parent_hash=_h(1))
    decision = svc.choose_and_apply([c2, c2b])
    assert decision.accepted
    assert svc.state.head.block_hash == _h(20)


def test_choose_and_apply_empty_rejects() -> None:
    svc = TipSafetyService(TipState(head=_b(0)))
    decision = svc.choose_and_apply([])
    assert decision.outcome == ApplyOutcome.REJECT
    assert decision.reason_code == "tip_validation"


def test_advance_finalized_ok() -> None:
    svc = TipSafetyService(TipState(head=_b(5)))
    svc.advance_finalized(_b(3))
    assert svc.state.finalized is not None
    assert svc.state.finalized.height == 3


def test_advance_finalized_regress_raises() -> None:
    svc = TipSafetyService(TipState(head=_b(5), finalized=_b(3)))
    with pytest.raises(TipFinalityRegressError):
        svc.advance_finalized(_b(2))


def test_service_rejects_bad_ctor_state() -> None:
    with pytest.raises(TipValidationError):
        TipSafetyService(state="nope")  # type: ignore[arg-type]


def test_network_partition_style_gap_rejected() -> None:
    """Simulate missing intermediate blocks (partition / catch-up gap)."""
    svc = TipSafetyService(TipState(head=_b(1)))
    far = BlockRef(height=50, block_hash=_h(50), parent_hash=_h(49))
    decision = svc.apply_candidate(far)
    assert decision.outcome == ApplyOutcome.REJECT
    assert decision.reason_code == "tip_unknown_parent"
    assert svc.state.head.height == 1
