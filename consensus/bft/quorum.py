"""Pure stake-weighted quorum policy (ADR 0007). No I/O."""

from __future__ import annotations

from typing import Iterable, Optional

from consensus.bft.types import (
    QuorumCertificate,
    RoundId,
    ValidatorSetSnapshot,
    Vote,
    VoteType,
)

QUORUM_THRESHOLD = 2.0 / 3.0


def quorum_reached(stake_voted: float, stake_total: float) -> bool:
    total = float(stake_total or 0.0)
    if total <= 0:
        return False
    return float(stake_voted or 0.0) / total >= QUORUM_THRESHOLD


def stake_for_votes(
    snapshot: ValidatorSetSnapshot,
    votes: Iterable[Vote],
    *,
    round_id: RoundId,
    vote_type: VoteType,
    block_hash: str,
) -> float:
    want = str(block_hash or "").strip().lower()
    seen = set()
    stake = 0.0
    for vote in votes:
        if vote.vote_type is not vote_type:
            continue
        if vote.round_id.key() != round_id.key():
            continue
        if str(vote.block_hash or "").lower() != want:
            continue
        vid = vote.validator_id
        if vid in seen:
            continue
        info = snapshot.get(vid)
        if info is None or not info.active or info.slashed:
            continue
        seen.add(vid)
        stake += float(info.stake or 0.0)
    return float(stake)


def build_certificate(
    snapshot: ValidatorSetSnapshot,
    votes: Iterable[Vote],
    *,
    round_id: RoundId,
    vote_type: VoteType,
    block_hash: str,
) -> Optional[QuorumCertificate]:
    total = float(snapshot.total_active_stake())
    if total <= 0:
        return QuorumCertificate(
            round_id=round_id,
            vote_type=vote_type,
            block_hash=str(block_hash or "").lower(),
            stake_voted=0.0,
            stake_total=0.0,
            reached=False,
        )
    voted = stake_for_votes(
        snapshot,
        votes,
        round_id=round_id,
        vote_type=vote_type,
        block_hash=block_hash,
    )
    return QuorumCertificate(
        round_id=round_id,
        vote_type=vote_type,
        block_hash=str(block_hash or "").lower(),
        stake_voted=voted,
        stake_total=total,
        reached=quorum_reached(voted, total),
    )


class QuorumPolicy:
    """Thin wrapper for RoundStateMachine."""

    threshold = QUORUM_THRESHOLD

    def certificate(
        self,
        snapshot: ValidatorSetSnapshot,
        votes: Iterable[Vote],
        *,
        round_id: RoundId,
        vote_type: VoteType,
        block_hash: str,
    ) -> QuorumCertificate:
        cert = build_certificate(
            snapshot,
            votes,
            round_id=round_id,
            vote_type=vote_type,
            block_hash=block_hash,
        )
        assert cert is not None
        return cert
