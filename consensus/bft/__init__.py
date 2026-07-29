"""BFT round domain package (ADR 0007)."""

from consensus.bft.evidence import (
    ConsensusMaliciousError,
    build_evidence,
    is_malicious_reason,
)
from consensus.bft.quorum import QuorumPolicy, quorum_reached
from consensus.bft.service import RoundStateMachine
from consensus.bft.types import (
    BlockRef,
    ConsensusSecurityEvidence,
    FinalityView,
    Proposal,
    QuorumCertificate,
    RoundId,
    RoundOutcome,
    RoundPhase,
    RoundStatus,
    ValidatorInfo,
    ValidatorSetSnapshot,
    Vote,
    VoteType,
)

__all__ = [
    "BlockRef",
    "ConsensusMaliciousError",
    "ConsensusSecurityEvidence",
    "FinalityView",
    "Proposal",
    "QuorumCertificate",
    "QuorumPolicy",
    "RoundId",
    "RoundOutcome",
    "RoundPhase",
    "RoundStateMachine",
    "RoundStatus",
    "ValidatorInfo",
    "ValidatorSetSnapshot",
    "Vote",
    "VoteType",
    "build_evidence",
    "is_malicious_reason",
    "quorum_reached",
]
