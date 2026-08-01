# tests/unit/test_finality_quorum_honesty.py
"""Live quorum reporting is armed-only; weak-subjectivity honesty surface."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from consensus.adapter import ConsensusAdapter
from consensus.bft.service import RoundStateMachine
from consensus.bft.types import QuorumCertificate, RoundId, VoteType


class _Reg:
    def validators(self):
        return []

    def total_stake(self):
        return 0.0


def test_round_sm_quorum_live_requires_arm_and_qc():
    sm = RoundStateMachine(
        registry=_Reg(),  # type: ignore[arg-type]
        evidence=MagicMock(),
        lockdown=MagicMock(),
    )
    view = sm.finality_status()
    assert view.quorum_live is False
    assert view.detail == "local_path_only"

    rid = RoundId(epoch=0, height=1, round=0)
    sm._qc[(rid.key(), VoteType.PRECOMMIT.value)] = QuorumCertificate(
        round_id=rid,
        vote_type=VoteType.PRECOMMIT,
        block_hash="0xabc",
        stake_voted=10.0,
        stake_total=10.0,
        reached=True,
    )
    sm.arm_quorum_live(True)
    view2 = sm.finality_status()
    assert view2.quorum_live is True
    assert view2.detail == "quorum_certificate_reached"


def test_adapter_weak_subjectivity_honesty():
    cfg = SimpleNamespace(
        finality_quorum_live=False,
        block_time=2,
        min_stake=0,
        consensus_mode="unified",
        deployment_mode="prod",
    )
    # Minimal stub — prefer constructing via existing factory if heavy;
    # exercise method on a lightweight stand-in.
    class _A:
        config = cfg

        def weak_subjectivity_status(self):
            return ConsensusAdapter.weak_subjectivity_status(self)  # type: ignore[arg-type]

    status = _A().weak_subjectivity_status()
    assert status["long_range_defense"] is False
    assert status["weak_subjectivity_checkpoints"] is False
    assert status["tip_ancestry_window"] is True
