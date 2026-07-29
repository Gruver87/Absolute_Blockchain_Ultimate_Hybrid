"""Pure fail-closed consistency state machine (no P2P / I/O)."""

from __future__ import annotations

import time
from typing import Optional, Sequence

from sync.consistency.types import (
    ConsistencyDecision,
    ConsistencyOutcome,
    ConsistencySnapshot,
    ConsistencyState,
    PeerSyncView,
    WireProbeResult,
)


class ConsistencyMachine:
    """Evaluate probe evidence into the next snapshot + decision.

    Incomplete-ahead (peers ahead, no same-height root match) → ``BEHIND_OPEN``
    with ``consistent=False`` and outcome that is **not** trusted success.
    """

    def boot_snapshot(self, *, now: Optional[float] = None) -> ConsistencySnapshot:
        return ConsistencySnapshot(
            state=ConsistencyState.UNKNOWN,
            consistent=False,
            probe=WireProbeResult.never_probed("boot"),
            reason_code="boot",
            updated_at=float(now if now is not None else time.time()),
        )

    def decide_from_snapshot(self, snap: ConsistencySnapshot) -> ConsistencyDecision:
        st = snap.state
        if st is ConsistencyState.CONSISTENT and snap.consistent:
            return ConsistencyDecision(
                outcome=ConsistencyOutcome.ALLOW_TRUSTED,
                state=st,
                reason_code=snap.reason_code or "ok",
                may_mine=True,
                may_serve_as_synced=True,
                may_catch_up=False,
                consistent=True,
            )
        if st is ConsistencyState.BEHIND_OPEN:
            return ConsistencyDecision(
                outcome=ConsistencyOutcome.ALLOW_CATCH_UP,
                state=st,
                reason_code=snap.reason_code or "behind_open",
                may_mine=False,
                may_serve_as_synced=False,
                may_catch_up=True,
                consistent=False,
            )
        if st is ConsistencyState.PROBING:
            return ConsistencyDecision(
                outcome=ConsistencyOutcome.ALLOW_CATCH_UP,
                state=st,
                reason_code=snap.reason_code or "probing",
                may_mine=False,
                may_serve_as_synced=False,
                may_catch_up=True,
                consistent=False,
            )
        # UNKNOWN / LOCKED_DOWN — deny trust; catch-up only after entering Probing.
        return ConsistencyDecision(
            outcome=ConsistencyOutcome.DENY,
            state=st,
            reason_code=snap.reason_code or st.value,
            may_mine=False,
            may_serve_as_synced=False,
            may_catch_up=False,
            consistent=False,
        )

    def evaluate_probe(
        self,
        current: ConsistencySnapshot,
        *,
        peers: Sequence[PeerSyncView],
        local_height: int,
        local_root: str,
        probe: WireProbeResult,
        now: Optional[float] = None,
    ) -> tuple[ConsistencySnapshot, ConsistencyDecision]:
        """Apply probe evidence; always fail-closed on anomaly."""
        ts = float(now if now is not None else time.time())
        lockdown_total = int(current.lockdown_total or 0)

        if not peers:
            snap = ConsistencySnapshot(
                state=ConsistencyState.UNKNOWN,
                consistent=False,
                probe=WireProbeResult.never_probed("no_peers"),
                reason_code="no_peers",
                updated_at=ts,
                lockdown_total=lockdown_total,
            )
            return snap, self.decide_from_snapshot(snap)

        if not probe.probed or probe.ok is not True:
            lockdown_total += 1
            reason = probe.detail or (
                "probe_never" if not probe.probed else "probe_failed"
            )
            snap = ConsistencySnapshot(
                state=ConsistencyState.LOCKED_DOWN,
                consistent=False,
                probe=probe,
                reason_code=reason,
                updated_at=ts,
                lockdown_total=lockdown_total,
            )
            return snap, self.decide_from_snapshot(snap)

        mismatches = list(probe.mismatch_peers)
        same_height_match = False
        for entry in probe.wire_roots:
            if not isinstance(entry, dict):
                continue
            peer_root = str(entry.get("state_root") or "")
            peer_h = int(entry.get("height", 0) or 0)
            if peer_h < int(local_height):
                continue
            if peer_h == int(local_height) and peer_root:
                if peer_root != str(local_root or ""):
                    pid = str(entry.get("peer_id") or "peer")[:8]
                    if pid not in mismatches:
                        mismatches.append(pid)
                else:
                    same_height_match = True

        if mismatches:
            lockdown_total += 1
            snap = ConsistencySnapshot(
                state=ConsistencyState.LOCKED_DOWN,
                consistent=False,
                probe=WireProbeResult(
                    probed=True,
                    ok=True,
                    wire_roots=probe.wire_roots,
                    mismatch_peers=tuple(mismatches),
                    detail=probe.detail,
                ),
                reason_code="state_root_mismatch",
                updated_at=ts,
                lockdown_total=lockdown_total,
            )
            return snap, self.decide_from_snapshot(snap)

        if not same_height_match:
            peers_ahead = any(int(p.height or 0) > int(local_height) for p in peers)
            if peers_ahead:
                # BehindOpen — NOT green / NOT trusted success.
                snap = ConsistencySnapshot(
                    state=ConsistencyState.BEHIND_OPEN,
                    consistent=False,
                    probe=probe,
                    reason_code="incomplete_ahead",
                    updated_at=ts,
                    lockdown_total=lockdown_total,
                )
                return snap, self.decide_from_snapshot(snap)
            lockdown_total += 1
            snap = ConsistencySnapshot(
                state=ConsistencyState.LOCKED_DOWN,
                consistent=False,
                probe=probe,
                reason_code="no_same_height_match",
                updated_at=ts,
                lockdown_total=lockdown_total,
            )
            return snap, self.decide_from_snapshot(snap)

        snap = ConsistencySnapshot(
            state=ConsistencyState.CONSISTENT,
            consistent=True,
            probe=probe,
            reason_code="ok",
            updated_at=ts,
            lockdown_total=lockdown_total,
        )
        return snap, self.decide_from_snapshot(snap)

    def lockdown(
        self,
        current: ConsistencySnapshot,
        reason_code: str,
        *,
        now: Optional[float] = None,
        probe: Optional[WireProbeResult] = None,
    ) -> ConsistencySnapshot:
        ts = float(now if now is not None else time.time())
        return ConsistencySnapshot(
            state=ConsistencyState.LOCKED_DOWN,
            consistent=False,
            probe=probe if probe is not None else current.probe,
            reason_code=str(reason_code or "lockdown"),
            updated_at=ts,
            lockdown_total=int(current.lockdown_total or 0) + 1,
        )

    def enter_probing(
        self,
        current: ConsistencySnapshot,
        *,
        now: Optional[float] = None,
    ) -> ConsistencySnapshot:
        ts = float(now if now is not None else time.time())
        return ConsistencySnapshot(
            state=ConsistencyState.PROBING,
            consistent=False,
            probe=current.probe,
            reason_code="probing",
            updated_at=ts,
            lockdown_total=int(current.lockdown_total or 0),
        )
