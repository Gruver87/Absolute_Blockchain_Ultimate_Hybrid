#!/usr/bin/env python3
"""Unit tests for ForkChoice."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from consensus.tip_safety.errors import TipValidationError
from consensus.tip_safety.fork_choice import ForkChoice
from consensus.tip_safety.types import BlockRef


def _b(height: int, n: int) -> BlockRef:
    h = f"{n:064x}"
    if height == 0:
        return BlockRef(height=0, block_hash=h, parent_hash="")
    return BlockRef(height=height, block_hash=h, parent_hash=f"{0:064x}")


def test_choose_prefers_higher_height() -> None:
    low = _b(1, 1)
    high = _b(3, 3)
    assert ForkChoice().choose([low, high]) == high


def test_choose_tie_break_by_hash() -> None:
    a = _b(5, 1)
    b = _b(5, 2)
    assert ForkChoice().choose([a, b]) == b


def test_choose_rejects_empty() -> None:
    with pytest.raises(TipValidationError):
        ForkChoice().choose([])


def test_choose_rejects_none() -> None:
    with pytest.raises(TipValidationError):
        ForkChoice().choose(None)  # type: ignore[arg-type]


def test_choose_rejects_non_blockref() -> None:
    with pytest.raises(TipValidationError):
        ForkChoice().choose([_b(1, 1), "x"])  # type: ignore[list-item]


def test_beats() -> None:
    low = _b(1, 1)
    high = _b(2, 2)
    fc = ForkChoice()
    assert fc.beats(high, low) is True
    assert fc.beats(low, high) is False
    assert fc.beats(low, low) is False
