#!/usr/bin/env python3
"""Unit tests for ReorgPolicy — positive and negative paths."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from consensus.tip_safety.errors import (
    TipAncestryError,
    TipDuplicateError,
    TipFinalityRegressError,
    TipUnknownParentError,
)
from consensus.tip_safety.reorg_policy import ReorgPolicy
from consensus.tip_safety.tip_state import TipState
from consensus.tip_safety.types import ApplyOutcome, BlockRef


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


def test_accept_extend() -> None:
    state = TipState(head=_b(1))
    cand = BlockRef(height=2, block_hash=_h(2), parent_hash=_h(1))
    decision = ReorgPolicy().evaluate(state, cand)
    assert decision.outcome == ApplyOutcome.ACCEPT_EXTEND
    assert decision.accepted
    assert decision.new_head == cand


def test_reject_duplicate() -> None:
    head = _b(1)
    state = TipState(head=head)
    with pytest.raises(TipDuplicateError):
        ReorgPolicy().evaluate(state, head)


def test_reject_extend_bad_parent() -> None:
    state = TipState(head=_b(1))
    cand = BlockRef(height=2, block_hash=_h(2), parent_hash=_h(99))
    with pytest.raises(TipAncestryError):
        ReorgPolicy().evaluate(state, cand)


def test_reject_below_finalized_floor() -> None:
    state = TipState(head=_b(10), finalized=_b(8))
    with pytest.raises(TipFinalityRegressError):
        ReorgPolicy().evaluate(state, _b(7))


def test_accept_same_height_reorg() -> None:
    head = BlockRef(height=5, block_hash=_h(5), parent_hash=_h(4))
    state = TipState(head=head, finalized=_b(3))
    rival = BlockRef(height=5, block_hash=_h(50), parent_hash=_h(4))
    decision = ReorgPolicy().evaluate(state, rival)
    assert decision.outcome == ApplyOutcome.ACCEPT_REORG


def test_reject_same_height_parent_mismatch() -> None:
    head = BlockRef(height=5, block_hash=_h(5), parent_hash=_h(4))
    state = TipState(head=head)
    rival = BlockRef(height=5, block_hash=_h(50), parent_hash=_h(3))
    with pytest.raises(TipAncestryError):
        ReorgPolicy().evaluate(state, rival)


def test_reject_replace_finalized_hash() -> None:
    fin = BlockRef(height=5, block_hash=_h(5), parent_hash=_h(4))
    state = TipState(head=fin, finalized=fin)
    rival = BlockRef(height=5, block_hash=_h(50), parent_hash=_h(4))
    with pytest.raises(TipFinalityRegressError):
        ReorgPolicy().evaluate(state, rival)


def test_reject_height_gap_unknown_parent() -> None:
    state = TipState(head=_b(1))
    cand = BlockRef(height=5, block_hash=_h(5), parent_hash=_h(4))
    with pytest.raises(TipUnknownParentError):
        ReorgPolicy().evaluate(state, cand)


def test_reject_deep_reorg_without_ancestry() -> None:
    state = TipState(head=_b(10), finalized=_b(2))
    with pytest.raises(TipUnknownParentError):
        ReorgPolicy().evaluate(state, _b(5))
