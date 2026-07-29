#!/usr/bin/env python3
"""ADR 0007 Wave B: RoundStateMachine fail-closed DoD."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from consensus.bft import (
    ConsensusMaliciousError,
    Proposal,
    RoundId,
    RoundPhase,
    RoundStateMachine,
    RoundStatus,
    Vote,
    VoteType,
)
from tests.unit.fakes.fake_consensus import (
    FakeConsensusEvidence,
    FakeConsensusLockdown,
    FakeConsensusSideEffect,
    FakeValidatorRegistry,
)

H = "aa" * 32
H2 = "bb" * 32
PARENT = "cc" * 32


def _sm(
    stakes: dict | None = None,
    *,
    expected_proposer: str = "v1",
):
    reg = FakeValidatorRegistry()
    for vid, stake in (stakes or {"v1": 40, "v2": 40, "v3": 40}).items():
        reg.register(vid, stake)
    ev = FakeConsensusEvidence()
    ld = FakeConsensusLockdown()
    side = FakeConsensusSideEffect()
    sm = RoundStateMachine(
        reg,
        ev,
        ld,
        side,
        expected_proposer=expected_proposer,
        epoch_size=32,
    )
    sm.open_round(1, expected_proposer=expected_proposer)
    return sm, reg, ev, ld, side


def _vote(vid: str, vt: VoteType, hh: str = H, round_id: RoundId | None = None):
    rid = round_id or RoundId(epoch=0, height=1, round=0)
    return Vote(
        validator_id=vid,
        vote_type=vt,
        round_id=rid,
        block_hash=hh,
        slot=1,
        verified=True,
    )


def test_happy_path_prevote_precommit_finalize():
    sm, _reg, _ev, ld, side = _sm()
    prop = Proposal(
        proposer_id="v1",
        round_id=sm.current_round(),
        block_hash=H,
        parent_hash=PARENT,
    )
    out = sm.submit_proposal(prop)
    assert out.ok
    assert out.phase is RoundPhase.PREVOTE

    for vid in ("v1", "v2", "v3"):
        out = sm.submit_vote(_vote(vid, VoteType.PREVOTE))
    assert out.phase is RoundPhase.PRECOMMIT
    assert sm.quorum_certificate(sm.current_round(), VoteType.PREVOTE).reached

    for vid in ("v1", "v2", "v3"):
        out = sm.submit_vote(_vote(vid, VoteType.PRECOMMIT))
    assert out.status is RoundStatus.COMPLETE
    assert sm.is_finalized(H)
    assert sm.finality_status().quorum_live is False
    assert ld.locked is False
    assert side.finalized


def test_double_vote_fail_closed_lockdown():
    sm, reg, ev, ld, _side = _sm()
    sm.submit_proposal(
        Proposal(
            proposer_id="v1",
            round_id=sm.current_round(),
            block_hash=H,
            parent_hash=PARENT,
        )
    )
    sm.submit_vote(_vote("v1", VoteType.PREVOTE, H))
    with pytest.raises(ConsensusMaliciousError) as ei:
        sm.submit_vote(_vote("v1", VoteType.PREVOTE, H2))
    assert ei.value.evidence.reason_code == "double_vote"
    assert sm.round_phase(sm.current_round()) is RoundPhase.LOCKED
    assert ld.locked is True
    assert ld.reasons[0] == "consensus_double_sign"
    assert ev.emitted
    assert any(s[0] == "v1" for s in reg.slash_log)


def test_unknown_validator_fail_closed():
    sm, _reg, ev, ld, _side = _sm()
    sm.submit_proposal(
        Proposal(
            proposer_id="v1",
            round_id=sm.current_round(),
            block_hash=H,
            parent_hash=PARENT,
        )
    )
    with pytest.raises(ConsensusMaliciousError) as ei:
        sm.submit_vote(_vote("evil", VoteType.PREVOTE, H))
    assert ei.value.evidence.reason_code == "unknown_validator_vote"
    assert sm.round_phase(sm.current_round()) is RoundPhase.LOCKED
    assert ev.emitted


def test_stale_round_refused_soft():
    sm, _reg, _ev, ld, _side = _sm()
    sm.submit_proposal(
        Proposal(
            proposer_id="v1",
            round_id=sm.current_round(),
            block_hash=H,
            parent_hash=PARENT,
        )
    )
    stale = RoundId(epoch=0, height=99, round=0)
    out = sm.submit_vote(_vote("v1", VoteType.PREVOTE, H, round_id=stale))
    assert out.status is RoundStatus.REFUSED
    assert out.reason_code == "stale_round_vote"
    assert ld.locked is False


def test_double_proposal_fail_closed():
    sm, _reg, ev, ld, _side = _sm()
    sm.submit_proposal(
        Proposal(
            proposer_id="v1",
            round_id=sm.current_round(),
            block_hash=H,
            parent_hash=PARENT,
        )
    )
    # Force phase back to propose for second conflicting proposal path:
    # after first proposal we are in PREVOTE; reopen and propose conflict via
    # submitting a second proposal while still tracking — use fresh SM.
    sm2, _r, ev2, ld2, _s = _sm()
    sm2.submit_proposal(
        Proposal(
            proposer_id="v1",
            round_id=sm2.current_round(),
            block_hash=H,
            parent_hash=PARENT,
        )
    )
    # Manually reset phase to PROPOSE with existing proposal to hit conflict.
    sm2._phase = RoundPhase.PROPOSE  # noqa: SLF001 — unit probe
    with pytest.raises(ConsensusMaliciousError) as ei:
        sm2.submit_proposal(
            Proposal(
                proposer_id="v1",
                round_id=sm2.current_round(),
                block_hash=H2,
                parent_hash=PARENT,
            )
        )
    assert ei.value.evidence.reason_code == "double_proposal"
    assert ld2.locked is True
    assert ev2.emitted


def test_empty_stake_never_finalizes():
    sm, _reg, _ev, ld, _side = _sm(stakes={"v1": 0, "v2": 0, "v3": 0})
    sm.submit_proposal(
        Proposal(
            proposer_id="v1",
            round_id=sm.current_round(),
            block_hash=H,
            parent_hash=PARENT,
        )
    )
    for vid in ("v1", "v2", "v3"):
        out = sm.submit_vote(_vote(vid, VoteType.PREVOTE))
    assert out.reason_code == "prevote_pending"
    assert not sm.is_finalized(H)
    assert ld.locked is False
