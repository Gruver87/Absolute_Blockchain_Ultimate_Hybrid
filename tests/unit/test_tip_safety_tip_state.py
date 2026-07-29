#!/usr/bin/env python3
"""Unit tests for TipState — tip-safety domain (stage 1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from consensus.tip_safety.errors import TipFinalityRegressError, TipValidationError
from consensus.tip_safety.tip_state import TipState
from consensus.tip_safety.types import BlockRef


def _hash(n: int) -> str:
    return f"{n:064x}"


def _block(height: int, *, parent: str | None = None) -> BlockRef:
    if height == 0:
        return BlockRef(height=0, block_hash=_hash(0), parent_hash="")
    parent_hash = parent if parent is not None else _hash(height - 1)
    return BlockRef(height=height, block_hash=_hash(height), parent_hash=parent_hash)


def test_construct_genesis_ok() -> None:
    state = TipState(head=_block(0))
    assert state.head.height == 0
    assert state.finalized is None
    assert state.finalized_floor_height() == 0


def test_construct_with_finalized_ok() -> None:
    head = _block(5)
    fin = _block(3)
    state = TipState(head=head, finalized=fin)
    assert state.finalized is not None
    assert state.finalized.height == 3
    assert state.can_reorg_to(3) is True
    assert state.can_reorg_to(2) is False


def test_reject_finalized_above_head() -> None:
    with pytest.raises(TipFinalityRegressError) as exc:
        TipState(head=_block(2), finalized=_block(5))
    assert exc.value.code == "tip_finality_regress"


def test_reject_non_blockref_head() -> None:
    with pytest.raises(TipValidationError):
        TipState(head="not-a-block")  # type: ignore[arg-type]


def test_with_head_extend_ok() -> None:
    state = TipState(head=_block(1))
    nxt = state.with_head(_block(2))
    assert nxt.head.height == 2
    assert state.head.height == 1  # immutability of previous instance


def test_with_head_below_finalized_rejected() -> None:
    state = TipState(head=_block(10), finalized=_block(8))
    with pytest.raises(TipFinalityRegressError):
        state.with_head(_block(7))


def test_with_head_replacing_finalized_hash_rejected() -> None:
    fin = _block(5)
    state = TipState(head=fin, finalized=fin)
    rival = BlockRef(height=5, block_hash=_hash(99), parent_hash=_hash(4))
    with pytest.raises(TipFinalityRegressError):
        state.with_head(rival)


def test_with_finalized_advance_ok() -> None:
    state = TipState(head=_block(10), finalized=_block(4))
    nxt = state.with_finalized(_block(6))
    assert nxt.finalized is not None
    assert nxt.finalized.height == 6
    assert state.finalized is not None
    assert state.finalized.height == 4


def test_with_finalized_regress_rejected() -> None:
    state = TipState(head=_block(10), finalized=_block(6))
    with pytest.raises(TipFinalityRegressError):
        state.with_finalized(_block(5))


def test_with_finalized_above_head_rejected() -> None:
    state = TipState(head=_block(4))
    with pytest.raises(TipFinalityRegressError):
        state.with_finalized(_block(9))


def test_with_finalized_same_height_hash_conflict() -> None:
    state = TipState(head=_block(5), finalized=_block(3))
    conflict = BlockRef(height=3, block_hash=_hash(99), parent_hash=_hash(2))
    with pytest.raises(TipFinalityRegressError):
        state.with_finalized(conflict)


def test_snapshot_isolation() -> None:
    state = TipState(head=_block(2), finalized=_block(1))
    snap = state.snapshot()
    _ = state.with_head(_block(3))
    assert snap.head.height == 2
    assert snap.finalized is not None
    assert snap.finalized.height == 1


def test_can_reorg_to_rejects_bad_height() -> None:
    state = TipState(head=_block(1))
    with pytest.raises(TipValidationError):
        state.can_reorg_to(-1)
    with pytest.raises(TipValidationError):
        state.can_reorg_to(True)  # type: ignore[arg-type]


def test_equality() -> None:
    a = TipState(head=_block(2), finalized=_block(1))
    b = TipState(head=_block(2), finalized=_block(1))
    c = TipState(head=_block(3), finalized=_block(1))
    assert a == b
    assert a != c


def test_repr_contains_heights() -> None:
    text = repr(TipState(head=_block(2), finalized=_block(1)))
    assert "TipState" in text
    assert "2/" in text
