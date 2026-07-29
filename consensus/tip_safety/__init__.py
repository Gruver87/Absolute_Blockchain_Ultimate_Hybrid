"""Tip-safety domain: canonical tip, finalized floor, reorg policy, fork-choice.

Stage 1: isolated domain + unit tests.
Stage 2: optional shadow observer on import path (``TIP_SAFETY_SHADOW``).
Stage 3: optional enforce on import path (``TIP_SAFETY_ENFORCE``; required in prod).

Public API::

    from consensus.tip_safety import (
        BlockRef,
        TipState,
        TipSafetyService,
        TipSafetyShadowObserver,
        ReorgPolicy,
        ForkChoice,
        TipSafetyError,
    )
"""

from __future__ import annotations

from consensus.tip_safety.errors import (
    TipAncestryError,
    TipConflictError,
    TipDuplicateError,
    TipFinalityRegressError,
    TipSafetyError,
    TipUnknownParentError,
    TipValidationError,
)
from consensus.tip_safety.fork_choice import ForkChoice
from consensus.tip_safety.reorg_policy import ReorgPolicy
from consensus.tip_safety.service import TipSafetyService
from consensus.tip_safety.shadow import (
    TipSafetyShadowObserver,
    block_ref_from_mapping,
    tip_state_from_chain,
)
from consensus.tip_safety.tip_state import TipState
from consensus.tip_safety.types import (
    ApplyDecision,
    ApplyOutcome,
    BlockRef,
    TipSnapshot,
    normalize_block_hash,
)

__all__ = [
    "ApplyDecision",
    "ApplyOutcome",
    "BlockRef",
    "ForkChoice",
    "ReorgPolicy",
    "TipAncestryError",
    "TipConflictError",
    "TipDuplicateError",
    "TipFinalityRegressError",
    "TipSafetyError",
    "TipSafetyService",
    "TipSafetyShadowObserver",
    "TipSnapshot",
    "TipState",
    "TipUnknownParentError",
    "TipValidationError",
    "block_ref_from_mapping",
    "normalize_block_hash",
    "tip_state_from_chain",
]
