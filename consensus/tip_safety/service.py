"""Application service for tip-safety evaluation and finality advance.

Pure domain orchestration: no DB, no P2P, no HTTP. Persistence adapters are
wired in a later stage; this service only mutates in-memory ``TipState``.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from consensus.tip_safety.errors import TipSafetyError, TipValidationError
from consensus.tip_safety.fork_choice import ForkChoice
from consensus.tip_safety.reorg_policy import ReorgPolicy
from consensus.tip_safety.tip_state import TipState
from consensus.tip_safety.types import ApplyDecision, ApplyOutcome, BlockRef

_LOG = logging.getLogger("abs.tip_safety")


class TipSafetyService:
    """Evaluate tip candidates and advance finality against a ``TipState``.

    Args:
        state: Mutable tip holder (thread-safe).
        reorg_policy: Policy used for single-candidate evaluation.
        fork_choice: Ranker for multi-candidate selection.
    """

    def __init__(
        self,
        state: TipState,
        reorg_policy: Optional[ReorgPolicy] = None,
        fork_choice: Optional[ForkChoice] = None,
    ) -> None:
        if not isinstance(state, TipState):
            raise TipValidationError(
                f"state must be TipState, got {type(state).__name__}"
            )
        self._state = state
        self._reorg = reorg_policy if reorg_policy is not None else ReorgPolicy()
        self._fork = fork_choice if fork_choice is not None else ForkChoice()
        if not isinstance(self._reorg, ReorgPolicy):
            raise TipValidationError("reorg_policy must be ReorgPolicy")
        if not isinstance(self._fork, ForkChoice):
            raise TipValidationError("fork_choice must be ForkChoice")

    @property
    def state(self) -> TipState:
        """Underlying tip state (same instance passed at construction)."""
        return self._state

    def evaluate_candidate(self, candidate: BlockRef) -> ApplyDecision:
        """Evaluate a candidate without mutating state.

        Args:
            candidate: Proposed tip block.

        Returns:
            Decision with ``accepted`` True/False. On policy rejection the
            decision uses ``ApplyOutcome.REJECT`` and does not raise, so
            callers can record metrics without try/except. Structural type
            errors still raise ``TipValidationError``.
        """
        try:
            return self._reorg.evaluate(self._state, candidate)
        except TipSafetyError as exc:
            _LOG.info(
                "evaluate_candidate reject code=%s detail=%s",
                exc.code,
                exc.message,
            )
            return ApplyDecision(
                outcome=ApplyOutcome.REJECT,
                reason_code=exc.code,
                detail=exc.message,
                new_head=None,
            )

    def apply_candidate(self, candidate: BlockRef) -> ApplyDecision:
        """Evaluate and, if accepted, update tip state.

        Args:
            candidate: Proposed tip block.

        Returns:
            Decision after optional state update.
        """
        decision = self.evaluate_candidate(candidate)
        if not decision.accepted or decision.new_head is None:
            return decision
        try:
            self._state = self._state.with_head(decision.new_head)
        except TipSafetyError as exc:
            _LOG.warning(
                "apply_candidate state update failed code=%s detail=%s",
                exc.code,
                exc.message,
            )
            return ApplyDecision(
                outcome=ApplyOutcome.REJECT,
                reason_code=exc.code,
                detail=exc.message,
                new_head=None,
            )
        _LOG.info(
            "tip applied outcome=%s height=%s hash=%s",
            decision.outcome.value,
            decision.new_head.height,
            decision.new_head.short_hash(),
        )
        return decision

    def choose_and_apply(self, candidates: Sequence[BlockRef]) -> ApplyDecision:
        """Pick the best candidate via fork-choice, then apply it.

        Args:
            candidates: Competing tip candidates.

        Returns:
            Apply decision for the winning candidate (or reject if empty/invalid).
        """
        try:
            winner = self._fork.choose(candidates)
        except TipValidationError as exc:
            return ApplyDecision(
                outcome=ApplyOutcome.REJECT,
                reason_code=exc.code,
                detail=exc.message,
                new_head=None,
            )
        return self.apply_candidate(winner)

    def advance_finalized(self, checkpoint: BlockRef) -> TipState:
        """Advance the finalized checkpoint fail-closed.

        Args:
            checkpoint: New finalized block reference.

        Returns:
            Updated tip state.

        Raises:
            TipSafetyError: Validation or finality regress.
        """
        self._state = self._state.with_finalized(checkpoint)
        _LOG.info(
            "finalized advanced height=%s hash=%s",
            checkpoint.height,
            checkpoint.short_hash(),
        )
        return self._state
