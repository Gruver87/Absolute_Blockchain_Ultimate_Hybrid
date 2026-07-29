"""Canonical tip + finalized floor state for Absolute tip-safety.

``TipState`` is an immutable-friendly domain object: mutation methods return a
new instance or raise a typed ``TipSafetyError``. No I/O, no P2P, no storage.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from consensus.tip_safety.errors import TipFinalityRegressError, TipValidationError
from consensus.tip_safety.types import BlockRef, TipSnapshot

_LOG = logging.getLogger("abs.tip_safety")


class TipState:
    """Thread-safe holder of canonical tip and optional finalized checkpoint.

    Invariants (enforced on every construction and update):

    * ``head`` is a valid ``BlockRef``.
    * If ``finalized`` is set, ``finalized.height <= head.height``.
    * Updates never lower the tip or finality below the finalized floor.

    Concurrent readers may call :meth:`snapshot` without holding external locks;
    writers serialize through an internal re-entrant lock.
    """

    __slots__ = ("_lock", "_head", "_finalized")

    def __init__(
        self,
        head: BlockRef,
        finalized: Optional[BlockRef] = None,
    ) -> None:
        """Create a tip state.

        Args:
            head: Canonical tip.
            finalized: Optional finalized checkpoint at or below ``head``.

        Raises:
            TipValidationError: Structural invariant violation.
            TipFinalityRegressError: Finalized height above head height.
        """
        self._lock = threading.RLock()
        self._head, self._finalized = self._validated_pair(head, finalized)

    @staticmethod
    def _validated_pair(
        head: BlockRef,
        finalized: Optional[BlockRef],
    ) -> tuple[BlockRef, Optional[BlockRef]]:
        if not isinstance(head, BlockRef):
            raise TipValidationError(
                f"head must be BlockRef, got {type(head).__name__}"
            )
        if finalized is not None and not isinstance(finalized, BlockRef):
            raise TipValidationError(
                f"finalized must be BlockRef or None, got {type(finalized).__name__}"
            )
        if finalized is not None and finalized.height > head.height:
            _LOG.warning(
                "reject tip state: finalized.height=%s > head.height=%s",
                finalized.height,
                head.height,
            )
            raise TipFinalityRegressError(
                "finalized height "
                f"{finalized.height} must be <= head height {head.height}"
            )
        return head, finalized

    @property
    def head(self) -> BlockRef:
        """Current canonical tip (copy-safe frozen ``BlockRef``)."""
        with self._lock:
            return self._head

    @property
    def finalized(self) -> Optional[BlockRef]:
        """Highest finalized checkpoint, or ``None`` if unset."""
        with self._lock:
            return self._finalized

    def snapshot(self) -> TipSnapshot:
        """Return an immutable snapshot for fork-choice / logging."""
        with self._lock:
            return TipSnapshot(head=self._head, finalized=self._finalized)

    def finalized_floor_height(self) -> int:
        """Return the minimum height a reorg target may use.

        Returns:
            Finalized height when a checkpoint exists; otherwise ``0``
            (genesis floor — reorgs that delete genesis are still rejected
            by ancestry rules elsewhere).
        """
        with self._lock:
            if self._finalized is None:
                return 0
            return self._finalized.height

    def can_reorg_to(self, candidate_height: int) -> bool:
        """Return whether a tip at ``candidate_height`` clears the finalized floor.

        Args:
            candidate_height: Proposed new tip height.

        Returns:
            ``True`` if the height is an int >= finalized floor.

        Raises:
            TipValidationError: Non-integer or negative height.
        """
        if not isinstance(candidate_height, int) or isinstance(candidate_height, bool):
            raise TipValidationError(
                f"candidate_height must be int, got {type(candidate_height).__name__}"
            )
        if candidate_height < 0:
            raise TipValidationError(
                f"candidate_height must be >= 0, got {candidate_height}"
            )
        floor = self.finalized_floor_height()
        return candidate_height >= floor

    def with_head(self, new_head: BlockRef) -> "TipState":
        """Return a new ``TipState`` with an updated tip.

        Args:
            new_head: Candidate canonical tip.

        Returns:
            New state sharing the same finalized checkpoint.

        Raises:
            TipValidationError: Invalid ``new_head``.
            TipFinalityRegressError: New tip below finalized floor.
        """
        if not isinstance(new_head, BlockRef):
            raise TipValidationError(
                f"new_head must be BlockRef, got {type(new_head).__name__}"
            )
        with self._lock:
            floor = (
                self._finalized.height if self._finalized is not None else 0
            )
            if self._finalized is not None and new_head.height < floor:
                _LOG.warning(
                    "reject with_head: height=%s < finalized_floor=%s hash=%s",
                    new_head.height,
                    floor,
                    new_head.short_hash(),
                )
                raise TipFinalityRegressError(
                    f"new head height {new_head.height} is below "
                    f"finalized floor {floor}"
                )
            if (
                self._finalized is not None
                and new_head.height == self._finalized.height
                and new_head.block_hash != self._finalized.block_hash
            ):
                _LOG.warning(
                    "reject with_head: hash conflict at finalized height=%s",
                    new_head.height,
                )
                raise TipFinalityRegressError(
                    "cannot replace finalized block at height "
                    f"{new_head.height}: "
                    f"{self._finalized.short_hash()} vs {new_head.short_hash()}"
                )
            return TipState(head=new_head, finalized=self._finalized)

    def with_finalized(self, checkpoint: BlockRef) -> "TipState":
        """Return a new ``TipState`` with an advanced finalized checkpoint.

        Finality may only move forward (same or higher height). Moving to a
        different hash at the same height is rejected fail-closed.

        Args:
            checkpoint: New finalized block reference.

        Returns:
            New state with updated finalized checkpoint.

        Raises:
            TipValidationError: Invalid checkpoint.
            TipFinalityRegressError: Height regress, above tip, or hash conflict.
        """
        if not isinstance(checkpoint, BlockRef):
            raise TipValidationError(
                f"checkpoint must be BlockRef, got {type(checkpoint).__name__}"
            )
        with self._lock:
            if checkpoint.height > self._head.height:
                _LOG.warning(
                    "reject with_finalized: checkpoint.height=%s > head.height=%s",
                    checkpoint.height,
                    self._head.height,
                )
                raise TipFinalityRegressError(
                    f"finalized height {checkpoint.height} cannot exceed "
                    f"head height {self._head.height}"
                )
            if self._finalized is not None:
                if checkpoint.height < self._finalized.height:
                    _LOG.warning(
                        "reject with_finalized: regress %s < %s",
                        checkpoint.height,
                        self._finalized.height,
                    )
                    raise TipFinalityRegressError(
                        f"finalized cannot regress from "
                        f"{self._finalized.height} to {checkpoint.height}"
                    )
                if (
                    checkpoint.height == self._finalized.height
                    and checkpoint.block_hash != self._finalized.block_hash
                ):
                    _LOG.warning(
                        "reject with_finalized: hash conflict at height %s",
                        checkpoint.height,
                    )
                    raise TipFinalityRegressError(
                        "finalized hash conflict at height "
                        f"{checkpoint.height}: "
                        f"{self._finalized.short_hash()} vs {checkpoint.short_hash()}"
                    )
            return TipState(head=self._head, finalized=checkpoint)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TipState):
            return NotImplemented
        snap_a = self.snapshot()
        snap_b = other.snapshot()
        return snap_a.head == snap_b.head and snap_a.finalized == snap_b.finalized

    def __repr__(self) -> str:
        snap = self.snapshot()
        fin = (
            f"{snap.finalized.height}/{snap.finalized.short_hash()}"
            if snap.finalized is not None
            else "None"
        )
        return (
            f"TipState(head={snap.head.height}/{snap.head.short_hash()}, "
            f"finalized={fin})"
        )
