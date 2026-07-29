"""ConsistencyService — single writer for sync trust state."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from sync.consistency.machine import ConsistencyMachine
from sync.consistency.types import (
    ConsistencyDecision,
    ConsistencySnapshot,
    ConsistencyState,
    PeerSyncView,
    WireProbeResult,
)
from sync.ports import SyncConsistencyStorePort


class ConsistencyService:
    """Evaluate probes and mutate the store (fail-closed)."""

    __slots__ = ("_store", "_machine")

    def __init__(
        self,
        store: SyncConsistencyStorePort,
        machine: Optional[ConsistencyMachine] = None,
    ) -> None:
        self._store = store
        self._machine = machine if machine is not None else ConsistencyMachine()

    @property
    def store(self) -> SyncConsistencyStorePort:
        return self._store

    def snapshot(self) -> ConsistencySnapshot:
        return self._store.get_snapshot()

    def decision(self) -> ConsistencyDecision:
        return self._machine.decide_from_snapshot(self.snapshot())

    def request_lockdown(self, reason_code: str) -> ConsistencyDecision:
        cur = self.snapshot()
        snap = self._machine.lockdown(cur, reason_code)
        self._store.set_snapshot(snap)
        return self._machine.decide_from_snapshot(snap)

    def request_probing(self) -> ConsistencyDecision:
        cur = self.snapshot()
        snap = self._machine.enter_probing(cur)
        self._store.set_snapshot(snap)
        return self._machine.decide_from_snapshot(snap)

    def apply_probe_evaluation(
        self,
        *,
        peers: Sequence[PeerSyncView],
        local_height: int,
        local_root: str,
        probe: WireProbeResult,
    ) -> ConsistencyDecision:
        cur = self.snapshot()
        snap, decision = self._machine.evaluate_probe(
            cur,
            peers=peers,
            local_height=int(local_height),
            local_root=str(local_root or ""),
            probe=probe,
        )
        self._store.set_snapshot(snap)
        return decision

    def status(self) -> dict[str, Any]:
        snap = self.snapshot()
        d = self._machine.decide_from_snapshot(snap)
        probe = snap.probe
        return {
            "consistency_boundary": True,
            "sync_consistency_state": snap.state.value,
            "state_consistent": bool(snap.consistent),
            "sync_consistency_reason": snap.reason_code,
            "sync_lockdown_total": int(snap.lockdown_total or 0),
            "wire_probe_probed": bool(probe.probed),
            "wire_probe_ok": probe.ok,
            "may_mine": bool(d.may_mine),
            "may_catch_up": bool(d.may_catch_up),
            "may_serve_as_synced": bool(d.may_serve_as_synced),
        }

    def merge_into_status(self, target: dict[str, Any]) -> dict[str, Any]:
        target.update(self.status())
        return target
