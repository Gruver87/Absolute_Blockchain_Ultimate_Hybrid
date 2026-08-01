"""Reorg policy relative to the finalized floor.

Stage-1 policy is deliberately strict: a candidate may become tip only if it
extends the current head (parent match) or is an explicit same-height replace
that still clears the finalized floor.

Stage-1.5 (ADR 0016): an optional ``AncestryWindow`` allows rollback to a
**known ancestor** already recorded in the window (above the finalized floor).
This is not a full DAG store and not Long-Range / BFT tip proof. Height gaps
ahead of tip still require sync fill (unknown-parent).
"""

from __future__ import annotations

import logging
from typing import Optional

from consensus.tip_safety.ancestry_window import AncestryWindow
from consensus.tip_safety.errors import (
    TipAncestryError,
    TipDuplicateError,
    TipFinalityRegressError,
    TipUnknownParentError,
    TipValidationError,
)
from consensus.tip_safety.tip_state import TipState
from consensus.tip_safety.types import ApplyDecision, ApplyOutcome, BlockRef

_LOG = logging.getLogger("abs.tip_safety")


class ReorgPolicy:
    """Evaluate whether a candidate block may replace or extend the tip.

    This policy does not perform I/O. Callers supply the live ``TipState``.
    """

    def __init__(self, ancestry: Optional[AncestryWindow] = None) -> None:
        self._ancestry = ancestry

    @property
    def ancestry(self) -> Optional[AncestryWindow]:
        return self._ancestry

    def evaluate(self, state: TipState, candidate: BlockRef) -> ApplyDecision:
        """Evaluate ``candidate`` against ``state``.

        Args:
            state: Current tip-safety state.
            candidate: Proposed new tip block.

        Returns:
            ``ApplyDecision`` describing accept-extend, accept-reorg, or reject.

        Raises:
            TipValidationError: ``state`` / ``candidate`` type errors.
            TipDuplicateError: Candidate identical to current head.
            TipFinalityRegressError: Candidate below finalized floor.
            TipUnknownParentError: Parent is not the current head (stage-1).
            TipAncestryError: Parent linkage / height inconsistency.
        """
        if not isinstance(state, TipState):
            raise TipValidationError(
                f"state must be TipState, got {type(state).__name__}"
            )
        if not isinstance(candidate, BlockRef):
            raise TipValidationError(
                f"candidate must be BlockRef, got {type(candidate).__name__}"
            )

        snap = state.snapshot()
        head = snap.head

        if (
            candidate.block_hash == head.block_hash
            and candidate.height == head.height
        ):
            _LOG.info(
                "reject duplicate tip height=%s hash=%s",
                candidate.height,
                candidate.short_hash(),
            )
            raise TipDuplicateError(
                f"candidate is identical to tip {head.short_hash()}@{head.height}"
            )

        if not state.can_reorg_to(candidate.height):
            floor = state.finalized_floor_height()
            _LOG.warning(
                "reject candidate below finalized floor height=%s floor=%s",
                candidate.height,
                floor,
            )
            raise TipFinalityRegressError(
                f"candidate height {candidate.height} is below finalized floor {floor}"
            )

        if (
            snap.finalized is not None
            and candidate.height == snap.finalized.height
            and candidate.block_hash != snap.finalized.block_hash
        ):
            _LOG.warning(
                "reject candidate replacing finalized hash at height=%s",
                candidate.height,
            )
            raise TipFinalityRegressError(
                "candidate would replace finalized block at height "
                f"{candidate.height}"
            )

        # Strict extend: next height, parent == current head hash.
        if candidate.height == head.height + 1:
            if candidate.parent_hash != head.block_hash:
                _LOG.warning(
                    "reject extend: parent mismatch want=%s got=%s",
                    head.short_hash(),
                    candidate.parent_hash[:12],
                )
                raise TipAncestryError(
                    "extend candidate parent_hash must equal current tip hash"
                )
            return ApplyDecision(
                outcome=ApplyOutcome.ACCEPT_EXTEND,
                reason_code="ok",
                detail=f"extend tip to {candidate.short_hash()}@{candidate.height}",
                new_head=candidate,
            )

        # Same-height competing tip: only allowed if parent matches prior parent
        # and clears finalized floor (already checked). Treated as reorg.
        if candidate.height == head.height:
            if candidate.parent_hash != head.parent_hash:
                _LOG.warning(
                    "reject same-height reorg: parent mismatch at height=%s",
                    candidate.height,
                )
                raise TipAncestryError(
                    "same-height reorg requires identical parent_hash"
                )
            if candidate.block_hash == head.block_hash:
                raise TipDuplicateError("candidate hash equals tip hash")
            return ApplyDecision(
                outcome=ApplyOutcome.ACCEPT_REORG,
                reason_code="ok",
                detail=(
                    f"same-height reorg to {candidate.short_hash()}@{candidate.height}"
                ),
                new_head=candidate,
            )

        # Height gap ahead of tip: sync must fill; window cannot invent parents.
        if candidate.height > head.height + 1:
            _LOG.warning(
                "reject unknown parent / height gap candidate=%s head=%s",
                candidate.height,
                head.height,
            )
            raise TipUnknownParentError(
                f"candidate height {candidate.height} skips ahead of tip "
                f"{head.height}; ancestry store required"
            )

        # candidate.height < head.height but >= finalized floor.
        # Stage-1.5: allow rollback only to a recorded ancestor in the window.
        if self._ancestry is not None:
            known = self._ancestry.get(candidate.block_hash)
            if (
                known is not None
                and int(known.height) == int(candidate.height)
                and self._ancestry.is_ancestor_of(head, candidate.block_hash)
            ):
                return ApplyDecision(
                    outcome=ApplyOutcome.ACCEPT_REORG,
                    reason_code="ok",
                    detail=(
                        f"window rollback to {candidate.short_hash()}"
                        f"@{candidate.height}"
                    ),
                    new_head=candidate,
                )

        _LOG.warning(
            "reject deep reorg without ancestry height=%s tip=%s",
            candidate.height,
            head.height,
        )
        raise TipUnknownParentError(
            f"deep reorg to height {candidate.height} from tip {head.height} "
            "requires ancestry verification (block not in tip ancestry window)"
        )
