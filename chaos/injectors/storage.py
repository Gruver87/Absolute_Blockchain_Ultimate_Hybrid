# chaos/injectors/storage.py — mid-UoW ENOSPC / corruption (ADR 0012)
"""Arm FakeStorage commit faults — tip must not advance on abort.

Simulates RocksDB-class failures at the StoragePort seam:
  - disk_full / enospc_mid_write → StorageFullError
  - corruption → StorageCorruptionError
"""

from __future__ import annotations

import threading
from typing import Optional

from chaos.ports import (
    FaultKind,
    InjectionOutcome,
    InjectionResult,
    InjectionSpec,
)


def _block_hash(seed: int, suffix: str = "aa") -> str:
    head = format(abs(int(seed)) % (16**8), "08x")
    body = (suffix * 32)[: 64 - len(head)]
    return (head + body)[:64]


class StorageChaosInjector:
    """ChaosPort wrapper over FakeStorage.inject_commit_fault."""

    KIND_MAP = {FaultKind.STORE_FULL, FaultKind.STORE_CORRUPT}

    def __init__(self, store=None) -> None:
        self._shared = store
        self.store = store
        self._armed: Optional[InjectionSpec] = None
        self._lock = threading.Lock()

    def arm(self, spec: InjectionSpec) -> None:
        self._armed = spec

    def disarm(self) -> None:
        self._armed = None
        store = self.store
        if store is not None and hasattr(store, "fail_next_commit"):
            store.fail_next_commit = ""
            store.sticky_commit_fault = ""
            if hasattr(store, "_mid_write_enospc_armed"):
                store._mid_write_enospc_armed = False

    def fire(self, spec: InjectionSpec) -> InjectionResult:
        with self._lock:
            return self._fire_locked(spec)

    def _fire_locked(self, spec: InjectionSpec) -> InjectionResult:
        try:
            from storage.types import BlockRecord, TipMeta
            from tests.unit.fakes.fake_storage import FakeStorage

            # Fresh store per fire avoids tip growth races under parallel waves.
            store = self._shared if self._shared is not None else FakeStorage()
            self.store = store
            tip_before = int(store.tip_height())

            if spec.kind == FaultKind.STORE_FULL:
                token = str(spec.params.get("token") or "disk_full")
                if token not in ("disk_full", "enospc_mid_write"):
                    token = "disk_full"
            elif spec.kind == FaultKind.STORE_CORRUPT:
                token = "corruption"
            else:
                return InjectionResult(
                    kind=spec.kind,
                    outcome=InjectionOutcome.PANIC.value,
                    detail="unsupported_kind",
                    wave_id=spec.wave_id,
                )

            store.inject_commit_fault(token, sticky=False)
            raised = False
            err_name = ""
            uow = None
            try:
                uow = store.begin_block_commit(
                    expected_parent="",
                    expected_tip_height=tip_before,
                )
                hx = _block_hash(spec.seed, "aa")
                uow.write_block(
                    BlockRecord.from_mapping(
                        {
                            "height": tip_before + 1,
                            "hash": hx,
                            "parent_hash": store.tip_hash() or ("00" * 32),
                            "state_root": "11" * 32,
                            "timestamp": 1,
                            "transactions": [],
                        }
                    )
                )
                uow.set_tip(
                    TipMeta(
                        height=tip_before + 1,
                        head_hash=hx,
                        state_root="11" * 32,
                    )
                )
                uow.commit()
            except Exception as exc:
                raised = True
                err_name = type(exc).__name__
                if uow is not None:
                    abort = getattr(uow, "abort", None)
                    if callable(abort):
                        try:
                            abort()
                        except Exception:
                            pass

            tip_after = int(store.tip_height())
            if raised and tip_after == tip_before:
                self.disarm()
                try:
                    uow2 = store.begin_block_commit(
                        expected_parent="",
                        expected_tip_height=tip_before,
                    )
                    hx2 = _block_hash(spec.seed, "bb")
                    parent = store.tip_hash() or ("00" * 32)
                    uow2.write_block(
                        BlockRecord.from_mapping(
                            {
                                "height": tip_before + 1,
                                "hash": hx2,
                                "parent_hash": parent,
                                "state_root": "22" * 32,
                                "timestamp": 2,
                                "transactions": [],
                            }
                        )
                    )
                    uow2.set_tip(
                        TipMeta(
                            height=tip_before + 1,
                            head_hash=hx2,
                            state_root="22" * 32,
                        )
                    )
                    uow2.commit()
                    return InjectionResult(
                        kind=spec.kind,
                        outcome=InjectionOutcome.RECOVERED.value,
                        detail=f"{err_name};token={token};tip_held_then_advanced",
                        wave_id=spec.wave_id,
                    )
                except Exception as exc2:
                    return InjectionResult(
                        kind=spec.kind,
                        outcome=InjectionOutcome.FAIL_CLOSED.value,
                        detail=f"{err_name};token={token};recover_failed:{type(exc2).__name__}",
                        wave_id=spec.wave_id,
                    )

            if raised and tip_after != tip_before:
                return InjectionResult(
                    kind=spec.kind,
                    outcome=InjectionOutcome.PANIC.value,
                    detail="tip_advanced_despite_fault",
                    wave_id=spec.wave_id,
                )
            if not raised:
                return InjectionResult(
                    kind=spec.kind,
                    outcome=InjectionOutcome.PANIC.value,
                    detail=f"fault_not_raised;token={token}",
                    wave_id=spec.wave_id,
                )
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.FAIL_CLOSED.value,
                detail=err_name or "aborted",
                wave_id=spec.wave_id,
            )
        except Exception as exc:
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail=f"uncaught:{exc!r}",
                wave_id=spec.wave_id,
            )
