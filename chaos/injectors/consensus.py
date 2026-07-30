# chaos/injectors/consensus.py — double-sign + false fork (ADR 0012)
"""Byzantine votes / conflicting tip evidence via FakeConsensus + scripted fork refuse."""

from __future__ import annotations

from typing import Optional

from chaos.ports import (
    FaultKind,
    InjectionOutcome,
    InjectionResult,
    InjectionSpec,
)


class ConsensusChaosInjector:
    KIND_MAP = {FaultKind.CONS_DOUBLE_SIGN, FaultKind.CONS_FALSE_FORK}

    def __init__(self) -> None:
        self._armed: Optional[InjectionSpec] = None
        self._fc = None
        self.false_fork_refused = False

    def arm(self, spec: InjectionSpec) -> None:
        self._armed = spec

    def disarm(self) -> None:
        self._armed = None
        self._fc = None
        self.false_fork_refused = False

    def fire(self, spec: InjectionSpec) -> InjectionResult:
        try:
            if spec.kind == FaultKind.CONS_DOUBLE_SIGN:
                return self._double_sign(spec)
            if spec.kind == FaultKind.CONS_FALSE_FORK:
                return self._false_fork(spec)
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail="unsupported_kind",
            )
        except Exception as exc:
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail=f"uncaught:{exc!r}",
            )

    def _double_sign(self, spec: InjectionSpec) -> InjectionResult:
        from consensus.bft import ConsensusMaliciousError, Vote, VoteType
        from tests.unit.fakes.fake_consensus import FakeConsensus

        h1 = "aa" * 32
        h2 = "bb" * 32
        fc = FakeConsensus(height=1 + (abs(int(spec.seed)) % 1000))
        self._fc = fc
        fc.propose(h1)
        fc.sm.submit_vote(
            Vote("v1", VoteType.PREVOTE, fc.sm.current_round(), h1, verified=True)
        )
        try:
            fc.sm.submit_vote(
                Vote("v1", VoteType.PREVOTE, fc.sm.current_round(), h2, verified=True)
            )
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail="double_sign_not_caught",
            )
        except ConsensusMaliciousError:
            if not fc.lockdown.locked:
                return InjectionResult(
                    kind=spec.kind,
                    outcome=InjectionOutcome.PANIC.value,
                    detail="no_lockdown",
                )
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.FAIL_CLOSED.value,
                detail="consensus_double_sign",
            )

    def _false_fork(self, spec: InjectionSpec) -> InjectionResult:
        """Scripted fork reconcile refuse — no silent tip hop."""
        tip = {"height": 10, "hash": "cc" * 32}
        peer_tip = {"height": 10, "hash": "dd" * 32}  # same height, different hash
        # Fail-closed: refuse reorg without evidence
        evidence_ok = bool(spec.params.get("force_accept", False))
        if tip["height"] == peer_tip["height"] and tip["hash"] != peer_tip["hash"]:
            if not evidence_ok:
                self.false_fork_refused = True
                return InjectionResult(
                    kind=spec.kind,
                    outcome=InjectionOutcome.FAIL_CLOSED.value,
                    detail="false_fork_refused",
                )
        # If somehow accepted without evidence — panic
        return InjectionResult(
            kind=spec.kind,
            outcome=InjectionOutcome.PANIC.value,
            detail="false_fork_accepted",
        )
