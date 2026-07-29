#!/usr/bin/env python3
"""Unit tests for tip-safety types and hash normalization."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from consensus.tip_safety.errors import TipValidationError
from consensus.tip_safety.types import (
    ApplyDecision,
    ApplyOutcome,
    BlockRef,
    normalize_block_hash,
)


def test_normalize_hash_strips_0x_and_lowercases() -> None:
    raw = "0x" + ("AB" * 32)
    assert normalize_block_hash(raw) == ("ab" * 32)


def test_normalize_hash_rejects_empty() -> None:
    with pytest.raises(TipValidationError):
        normalize_block_hash("")
    with pytest.raises(TipValidationError):
        normalize_block_hash("   ")


def test_normalize_hash_rejects_wrong_length() -> None:
    with pytest.raises(TipValidationError):
        normalize_block_hash("abcd")
    with pytest.raises(TipValidationError):
        normalize_block_hash("zz" * 32)


def test_normalize_hash_rejects_none_and_non_str() -> None:
    with pytest.raises(TipValidationError):
        normalize_block_hash(None)  # type: ignore[arg-type]
    with pytest.raises(TipValidationError):
        normalize_block_hash(123)  # type: ignore[arg-type]


def test_blockref_genesis_ok() -> None:
    b = BlockRef(height=0, block_hash="0x" + ("11" * 32), parent_hash="")
    assert b.block_hash == "11" * 32
    assert b.parent_hash == ""


def test_blockref_non_genesis_requires_parent() -> None:
    with pytest.raises(TipValidationError):
        BlockRef(height=1, block_hash="22" * 32, parent_hash="")


def test_blockref_rejects_negative_height() -> None:
    with pytest.raises(TipValidationError):
        BlockRef(height=-1, block_hash="11" * 32)


def test_blockref_rejects_bool_height() -> None:
    with pytest.raises(TipValidationError):
        BlockRef(height=True, block_hash="11" * 32)  # type: ignore[arg-type]


def test_apply_decision_accepted_property() -> None:
    head = BlockRef(height=0, block_hash="11" * 32)
    ok = ApplyDecision(
        outcome=ApplyOutcome.ACCEPT_EXTEND,
        reason_code="ok",
        detail="x",
        new_head=head,
    )
    bad = ApplyDecision(
        outcome=ApplyOutcome.REJECT,
        reason_code="tip_validation",
        detail="no",
    )
    assert ok.accepted is True
    assert bad.accepted is False
