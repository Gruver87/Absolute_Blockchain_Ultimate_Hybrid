"""Deterministic fork-choice among competing tip candidates.

Stage-1 rule (KISS, deployable, testable):

1. Prefer higher ``height``.
2. On equal height, prefer lexicographically greater ``block_hash``.
3. All candidates must already clear ``ReorgPolicy`` individually when applied;
   this module only ranks pre-validated ``BlockRef`` values.

No network I/O. No random tie-breaks.
"""

from __future__ import annotations

import logging
from typing import Sequence

from consensus.tip_safety.errors import TipValidationError
from consensus.tip_safety.types import BlockRef

_LOG = logging.getLogger("abs.tip_safety")


class ForkChoice:
    """Select a single head from a non-empty sequence of block references."""

    def choose(self, candidates: Sequence[BlockRef]) -> BlockRef:
        """Return the winning tip among ``candidates``.

        Args:
            candidates: One or more ``BlockRef`` values.

        Returns:
            The selected canonical tip reference.

        Raises:
            TipValidationError: Empty input or non-``BlockRef`` elements.
        """
        if candidates is None:
            raise TipValidationError("candidates must be a sequence, got None")
        if not isinstance(candidates, (list, tuple)):
            try:
                material = list(candidates)
            except TypeError as exc:
                raise TipValidationError(
                    f"candidates must be a sequence: {exc}"
                ) from exc
        else:
            material = list(candidates)

        if not material:
            raise TipValidationError("candidates must not be empty")

        for index, item in enumerate(material):
            if not isinstance(item, BlockRef):
                raise TipValidationError(
                    f"candidates[{index}] must be BlockRef, "
                    f"got {type(item).__name__}"
                )

        # Total order: height desc, then hash desc — always decisive.
        winner = max(material, key=lambda b: (b.height, b.block_hash))
        _LOG.debug(
            "fork_choice winner height=%s hash=%s from=%s",
            winner.height,
            winner.short_hash(),
            len(material),
        )
        return winner

    def beats(self, left: BlockRef, right: BlockRef) -> bool:
        """Return True if ``left`` ranks strictly above ``right``.

        Args:
            left: First candidate.
            right: Second candidate.

        Returns:
            Strict preference of ``left`` over ``right``.

        Raises:
            TipValidationError: Either argument is not a ``BlockRef``.
        """
        if not isinstance(left, BlockRef) or not isinstance(right, BlockRef):
            raise TipValidationError("beats() requires two BlockRef arguments")
        if left == right:
            return False
        return self.choose((left, right)) == left
