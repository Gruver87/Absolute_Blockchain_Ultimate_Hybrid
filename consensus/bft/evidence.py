"""Consensus security evidence (ADR 0007). No P2P imports."""

from __future__ import annotations

from typing import Optional, Sequence

from consensus.bft.types import (
    ConsensusSecurityEvidence,
    RoundId,
    RoundOutcome,
    Vote,
)

MALICIOUS_REASON_CODES = frozenset(
    {
        "double_vote",
        "double_proposal",
        "surround_vote",
        "unknown_validator_vote",
        "fake_vote_unverified",
        "consensus_double_sign",
        "consensus_round_spam",
        "prevote_precommit_hash_mismatch",
    }
)

_SPAM_THRESHOLD = 3


class ConsensusMaliciousError(Exception):
    """Raised after Evidence + side effects on a fail-closed consensus path."""

    def __init__(
        self,
        outcome: RoundOutcome,
        evidence: ConsensusSecurityEvidence,
    ) -> None:
        self.outcome = outcome
        self.evidence = evidence
        super().__init__(
            f"fail-closed consensus refuse validator={evidence.validator_id[:12]} "
            f"reason={outcome.reason_code}"
        )


def is_malicious_reason(reason_code: str) -> bool:
    return str(reason_code or "") in MALICIOUS_REASON_CODES


def build_evidence(
    *,
    reason_code: str,
    validator_id: str,
    round_id: Optional[RoundId] = None,
    conflicting_votes: Sequence[Vote] = (),
    attempt_count: int = 1,
    detail: str = "",
) -> ConsensusSecurityEvidence:
    return ConsensusSecurityEvidence(
        reason_code=str(reason_code or "refused"),
        validator_id=str(validator_id or ""),
        round_id=round_id,
        conflicting_votes=tuple(conflicting_votes or ()),
        attempt_count=max(1, int(attempt_count or 1)),
        detail=str(detail or ""),
    )


def spam_threshold() -> int:
    return int(_SPAM_THRESHOLD)
