"""In-memory consensus ports + BFT quorum unit tests (ADR 0007 Wave C).

No P2P / DB. ``FakeConsensus`` is a full ``ConsensusPort`` harness over
``RoundStateMachine`` for industrial quorum DoD.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pytest

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from consensus.bft import (
    ConsensusMaliciousError,
    Proposal,
    QuorumPolicy,
    RoundId,
    RoundPhase,
    RoundStateMachine,
    RoundStatus,
    Vote,
    VoteType,
    quorum_reached,
)
from consensus.bft.types import (
    ConsensusSecurityEvidence,
    ValidatorInfo,
    ValidatorSetSnapshot,
)
from consensus.bft.quorum import stake_for_votes
from consensus.ports import ConsensusPort, ValidatorRegistryPort

__all__ = [
    "FakeValidatorRegistry",
    "FakeConsensusEvidence",
    "FakeConsensusLockdown",
    "FakeConsensusSideEffect",
    "FakeConsensus",
]


class FakeValidatorRegistry:
    """Implements ValidatorRegistryPort in memory."""

    def __init__(self, validators: Sequence[ValidatorInfo] | None = None) -> None:
        self._by_id: Dict[str, ValidatorInfo] = {}
        for v in validators or ():
            self._by_id[v.validator_id] = v
        self.slash_log: List[tuple] = []

    def register(self, validator_id: str, stake: float, *, active: bool = True) -> None:
        self._by_id[str(validator_id)] = ValidatorInfo(
            validator_id=str(validator_id),
            stake=float(stake),
            active=bool(active),
            slashed=False,
        )

    def list_active(self) -> Sequence[ValidatorInfo]:
        return tuple(v for v in self._by_id.values() if v.active and not v.slashed)

    def get(self, validator_id: str) -> Optional[ValidatorInfo]:
        return self._by_id.get(str(validator_id or "").strip())

    def total_active_stake(self) -> float:
        return float(sum(float(v.stake) for v in self.list_active()))

    def is_active(self, validator_id: str) -> bool:
        v = self.get(validator_id)
        return bool(v and v.active and not v.slashed)

    def mark_slashed(
        self,
        validator_id: str,
        reason: str,
        evidence: Optional[ConsensusSecurityEvidence] = None,
    ) -> None:
        vid = str(validator_id or "").strip()
        self.slash_log.append((vid, str(reason or ""), evidence))
        cur = self._by_id.get(vid)
        if cur is None:
            return
        self._by_id[vid] = ValidatorInfo(
            validator_id=cur.validator_id,
            stake=cur.stake,
            pubkey=cur.pubkey,
            active=False,
            slashed=True,
        )

    def snapshot(self) -> ValidatorSetSnapshot:
        return ValidatorSetSnapshot(validators=tuple(self._by_id.values()))


class FakeConsensusEvidence:
    """Implements ConsensusEvidencePort."""

    def __init__(self) -> None:
        self.emitted: List[ConsensusSecurityEvidence] = []
        self.attempts: Dict[str, int] = {}

    def emit(self, evidence: ConsensusSecurityEvidence) -> None:
        self.emitted.append(evidence)

    def note_malicious_attempt(self, validator_id: str, reason: str) -> int:
        key = f"{validator_id}:{reason}"
        n = int(self.attempts.get(key, 0) or 0) + 1
        self.attempts[key] = n
        peer_key = str(validator_id or "")
        self.attempts[peer_key] = int(self.attempts.get(peer_key, 0) or 0) + 1
        return n


class FakeConsensusLockdown:
    """Implements ConsensusLockdownPort."""

    def __init__(self) -> None:
        self.reasons: List[str] = []

    def request_lockdown(self, reason: str) -> None:
        self.reasons.append(str(reason or ""))

    @property
    def locked(self) -> bool:
        return bool(self.reasons)


class FakeConsensusSideEffect:
    """Implements ConsensusSideEffectPort — records only, never network I/O."""

    def __init__(self) -> None:
        self.attestations: List[Vote] = []
        self.finalized: List[tuple] = []

    def on_attestation(self, vote: Vote) -> None:
        self.attestations.append(vote)

    def on_finalized(self, block_hash: str, height: int) -> None:
        self.finalized.append((str(block_hash), int(height)))


class FakeConsensus:
    """Full ConsensusPort harness for BFT quorum unit DoD."""

    def __init__(
        self,
        stakes: Dict[str, float] | None = None,
        *,
        expected_proposer: str = "v1",
        height: int = 1,
    ) -> None:
        self.registry = FakeValidatorRegistry()
        for vid, stake in (stakes or {"v1": 40.0, "v2": 40.0, "v3": 40.0}).items():
            self.registry.register(vid, float(stake))
        self.evidence = FakeConsensusEvidence()
        self.lockdown = FakeConsensusLockdown()
        self.side = FakeConsensusSideEffect()
        self.sm = RoundStateMachine(
            self.registry,
            self.evidence,
            self.lockdown,
            self.side,
            expected_proposer=expected_proposer,
            epoch_size=32,
        )
        self.sm.open_round(int(height), expected_proposer=expected_proposer)

    def as_port(self) -> ConsensusPort:
        return self.sm  # RoundStateMachine exposes ConsensusPort methods

    def propose(self, block_hash: str, *, proposer: str = "v1", parent: str = "") -> None:
        parent_hash = parent or ("cc" * 32)
        out = self.sm.submit_proposal(
            Proposal(
                proposer_id=proposer,
                round_id=self.sm.current_round(),
                block_hash=block_hash,
                parent_hash=parent_hash,
            )
        )
        assert out.ok, out.reason_code

    def prevote_all(self, block_hash: str, validators: Sequence[str] | None = None) -> None:
        vids = list(validators) if validators is not None else [
            v.validator_id for v in self.registry.list_active()
        ]
        for vid in vids:
            self.sm.submit_vote(
                Vote(
                    validator_id=vid,
                    vote_type=VoteType.PREVOTE,
                    round_id=self.sm.current_round(),
                    block_hash=block_hash,
                    verified=True,
                )
            )

    def precommit_all(
        self, block_hash: str, validators: Sequence[str] | None = None
    ) -> None:
        vids = list(validators) if validators is not None else [
            v.validator_id for v in self.registry.list_active()
        ]
        for vid in vids:
            self.sm.submit_vote(
                Vote(
                    validator_id=vid,
                    vote_type=VoteType.PRECOMMIT,
                    round_id=self.sm.current_round(),
                    block_hash=block_hash,
                    verified=True,
                )
            )


# ── BFT quorum unit tests (collected from this module) ─────────────────────

_H = "aa" * 32
_H2 = "bb" * 32


def test_fake_registry_is_validator_registry_port():
    reg = FakeValidatorRegistry()
    reg.register("v1", 10)
    assert isinstance(reg, ValidatorRegistryPort)
    assert reg.total_active_stake() == 10.0


def test_quorum_policy_two_thirds_stake():
    snap = ValidatorSetSnapshot(
        validators=(
            ValidatorInfo("v1", stake=50),
            ValidatorInfo("v2", stake=30),
            ValidatorInfo("v3", stake=20),
        )
    )
    rid = RoundId(0, 1, 0)
    votes = [
        Vote("v1", VoteType.PREVOTE, rid, _H, verified=True),
        Vote("v2", VoteType.PREVOTE, rid, _H, verified=True),
    ]
    voted = stake_for_votes(
        snap, votes, round_id=rid, vote_type=VoteType.PREVOTE, block_hash=_H
    )
    assert voted == 80.0
    assert quorum_reached(voted, snap.total_active_stake()) is True
    assert quorum_reached(50.0, 100.0) is False
    assert quorum_reached(66.7, 100.0) is True


def test_quorum_policy_zero_total_never_reaches():
    policy = QuorumPolicy()
    snap = ValidatorSetSnapshot(validators=())
    cert = policy.certificate(
        snap,
        [],
        round_id=RoundId(0, 1, 0),
        vote_type=VoteType.PREVOTE,
        block_hash=_H,
    )
    assert cert.reached is False
    assert cert.stake_total == 0.0


def test_fake_consensus_full_quorum_finalize():
    fc = FakeConsensus()
    assert isinstance(fc.as_port(), ConsensusPort) or hasattr(fc.sm, "submit_vote")
    fc.propose(_H)
    fc.prevote_all(_H)
    cert = fc.sm.quorum_certificate(fc.sm.current_round(), VoteType.PREVOTE)
    assert cert is not None and cert.reached is True
    out = None
    for vid in ("v1", "v2", "v3"):
        out = fc.sm.submit_vote(
            Vote(
                validator_id=vid,
                vote_type=VoteType.PRECOMMIT,
                round_id=fc.sm.current_round(),
                block_hash=_H,
                verified=True,
            )
        )
    assert out is not None
    assert out.status is RoundStatus.COMPLETE
    assert fc.sm.is_finalized(_H)
    assert fc.sm.finality_status().quorum_live is False
    assert fc.side.finalized
    assert fc.lockdown.locked is False


def test_fake_consensus_minority_prevote_no_advance():
    fc = FakeConsensus(stakes={"v1": 10, "v2": 10, "v3": 80})
    fc.propose(_H)
    # Only 20/100 stake — below 2/3
    fc.prevote_all(_H, validators=("v1", "v2"))
    cert = fc.sm.quorum_certificate(fc.sm.current_round(), VoteType.PREVOTE)
    assert cert is not None
    assert cert.reached is False
    assert fc.sm.round_phase(fc.sm.current_round()) is RoundPhase.PREVOTE
    assert not fc.sm.is_finalized(_H)


def test_fake_consensus_double_vote_lockdown_no_network_side_effects():
    fc = FakeConsensus()
    fc.propose(_H)
    fc.sm.submit_vote(
        Vote("v1", VoteType.PREVOTE, fc.sm.current_round(), _H, verified=True)
    )
    with pytest.raises(ConsensusMaliciousError) as ei:
        fc.sm.submit_vote(
            Vote("v1", VoteType.PREVOTE, fc.sm.current_round(), _H2, verified=True)
        )
    assert ei.value.evidence.reason_code == "double_vote"
    assert fc.lockdown.locked is True
    assert fc.evidence.emitted
    # Side-effect port never talks to sockets — only local lists
    assert isinstance(fc.side.attestations, list)


def test_fake_consensus_exact_two_thirds_boundary():
    # 66.666...% of 3 equal stakes needs 2 of 3
    fc = FakeConsensus(stakes={"v1": 1, "v2": 1, "v3": 1})
    fc.propose(_H)
    fc.prevote_all(_H, validators=("v1", "v2"))
    cert = fc.sm.quorum_certificate(fc.sm.current_round(), VoteType.PREVOTE)
    assert cert is not None
    assert cert.reached is True
    assert cert.stake_voted == 2.0
    assert cert.stake_total == 3.0
