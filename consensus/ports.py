"""Consensus domain ports (ADR 0007). No ``network.p2p_node`` imports."""

from __future__ import annotations

from typing import Optional, Protocol, Sequence, runtime_checkable

from consensus.bft.types import (
    BlockRef,
    ConsensusSecurityEvidence,
    FinalityView,
    Proposal,
    QuorumCertificate,
    RoundId,
    RoundOutcome,
    RoundPhase,
    ValidatorInfo,
    ValidatorSetSnapshot,
    Vote,
    VoteType,
)


@runtime_checkable
class ValidatorRegistryPort(Protocol):
    """Active validator set — no live DB mid-round."""

    def list_active(self) -> Sequence[ValidatorInfo]:
        ...

    def get(self, validator_id: str) -> Optional[ValidatorInfo]:
        ...

    def total_active_stake(self) -> float:
        ...

    def is_active(self, validator_id: str) -> bool:
        ...

    def mark_slashed(
        self,
        validator_id: str,
        reason: str,
        evidence: Optional[ConsensusSecurityEvidence] = None,
    ) -> None:
        ...

    def snapshot(self) -> ValidatorSetSnapshot:
        ...


@runtime_checkable
class ConsensusEvidencePort(Protocol):
    def emit(self, evidence: ConsensusSecurityEvidence) -> None:
        ...

    def note_malicious_attempt(self, validator_id: str, reason: str) -> int:
        ...


@runtime_checkable
class ConsensusLockdownPort(Protocol):
    def request_lockdown(self, reason: str) -> None:
        ...


@runtime_checkable
class ConsensusSideEffectPort(Protocol):
    def on_attestation(self, vote: Vote) -> None:
        ...

    def on_finalized(self, block_hash: str, height: int) -> None:
        ...


@runtime_checkable
class ConsensusPort(Protocol):
    """Domain consensus ingress/queries (already-verified votes)."""

    def submit_proposal(self, proposal: Proposal) -> RoundOutcome:
        ...

    def submit_vote(self, vote: Vote) -> RoundOutcome:
        ...

    def current_round(self) -> RoundId:
        ...

    def round_phase(self, round_id: RoundId) -> RoundPhase:
        ...

    def canonical_head(self) -> Optional[BlockRef]:
        ...

    def is_finalized(self, block_hash_or_height: str | int) -> bool:
        ...

    def finality_status(self) -> FinalityView:
        ...

    def quorum_certificate(
        self, round_id: RoundId, vote_type: VoteType
    ) -> Optional[QuorumCertificate]:
        ...

    def add_block(self, block_ref: BlockRef, parent_hash: str = "") -> None:
        ...

    def get_attestations_for_block(self, block_hash: str) -> Sequence[Vote]:
        ...
