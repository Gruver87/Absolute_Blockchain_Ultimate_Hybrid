"""Immutable value types for the tip-safety domain.

These types carry no I/O. They are safe to share across threads as long as
callers treat instances as read-only (frozen dataclasses).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from consensus.tip_safety.errors import TipValidationError

# Canonical 32-byte digest: optional 0x prefix, exactly 64 hex digits.
_HASH_RE = re.compile(r"^(?:0x)?([0-9a-fA-F]{64})$")


def normalize_block_hash(raw: str) -> str:
    """Normalize a block hash to lowercase 64-hex without ``0x``.

    Args:
        raw: Candidate hash string from wire, DB, or API.

    Returns:
        Lowercase 64-character hex digest.

    Raises:
        TipValidationError: If ``raw`` is empty, wrong length, or non-hex.
    """
    if raw is None:
        raise TipValidationError("block hash must be a string, got None")
    if not isinstance(raw, str):
        raise TipValidationError(
            f"block hash must be a string, got {type(raw).__name__}"
        )
    text = raw.strip()
    if not text:
        raise TipValidationError("block hash must not be empty")
    match = _HASH_RE.fullmatch(text)
    if match is None:
        raise TipValidationError(
            "block hash must be 64 hex chars (optional 0x prefix), "
            f"got length={len(text)}"
        )
    return match.group(1).lower()


@dataclass(frozen=True, slots=True)
class BlockRef:
    """Reference to a single block on the chain.

    Attributes:
        height: Non-negative block height (genesis = 0).
        block_hash: Canonical lowercase 64-hex digest (no ``0x``).
        parent_hash: Parent digest, or empty string for genesis (height 0).
    """

    height: int
    block_hash: str
    parent_hash: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.height, int) or isinstance(self.height, bool):
            raise TipValidationError(
                f"height must be int, got {type(self.height).__name__}"
            )
        if self.height < 0:
            raise TipValidationError(f"height must be >= 0, got {self.height}")
        object.__setattr__(self, "block_hash", normalize_block_hash(self.block_hash))
        if self.height == 0:
            parent = (self.parent_hash or "").strip()
            if parent in ("", "0" * 64, "0x" + "0" * 64):
                object.__setattr__(self, "parent_hash", "")
            else:
                object.__setattr__(
                    self, "parent_hash", normalize_block_hash(self.parent_hash)
                )
        else:
            if not (self.parent_hash or "").strip():
                raise TipValidationError(
                    f"non-genesis block at height {self.height} requires parent_hash"
                )
            object.__setattr__(
                self, "parent_hash", normalize_block_hash(self.parent_hash)
            )

    def short_hash(self) -> str:
        """Return a short prefix of the digest for logs."""
        return self.block_hash[:12]


@dataclass(frozen=True, slots=True)
class TipSnapshot:
    """Immutable view of tip-safety state at a point in time.

    Attributes:
        head: Canonical tip block.
        finalized: Highest finalized checkpoint, if any.
    """

    head: BlockRef
    finalized: Optional[BlockRef]


class ApplyOutcome(str, Enum):
    """Result classification for evaluating a tip candidate."""

    ACCEPT_EXTEND = "accept_extend"
    ACCEPT_REORG = "accept_reorg"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ApplyDecision:
    """Outcome of evaluating a block candidate against tip-safety policy.

    Attributes:
        outcome: Accept extend, accept reorg, or reject.
        reason_code: Stable code for metrics (``ok`` or a ``TipSafetyError.code``).
        detail: Human-readable explanation.
        new_head: Head after accept; ``None`` on reject.
    """

    outcome: ApplyOutcome
    reason_code: str
    detail: str
    new_head: Optional[BlockRef] = None

    @property
    def accepted(self) -> bool:
        """True when the candidate should become the new tip."""
        return self.outcome in (
            ApplyOutcome.ACCEPT_EXTEND,
            ApplyOutcome.ACCEPT_REORG,
        )
