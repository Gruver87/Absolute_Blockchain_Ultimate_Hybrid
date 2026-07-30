# chaos/engine.py — TotalChaosEngine async coordinated bombardment (ADR 0012)
"""Parallel + coordinated FaultKind firing through ChaosPort injectors.

Lab/test-only. ``refuse_prod_arming`` blocks deployment_mode=prod.
Coordinated waves fire NETWORK + STORAGE + CONSENSUS + BRIDGE_RPC in the same
``asyncio.gather`` tick so domains fail together under observer gauges.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence

from chaos.injectors.bridge_rpc import BridgeRpcChaosInjector
from chaos.injectors.consensus import ConsensusChaosInjector
from chaos.injectors.network import NetworkChaosInjector
from chaos.injectors.storage import StorageChaosInjector
from chaos.observer import ChaosObserver
from chaos.ports import (
    FAMILY_KINDS,
    ChaosObserverPort,
    ChaosPort,
    ChaosReport,
    CoordinatedWave,
    FaultFamily,
    FaultKind,
    InjectionOutcome,
    InjectionResult,
    InjectionSpec,
)

_DEFAULT_WEIGHTS: Mapping[FaultKind, float] = {
    FaultKind.NET_TEAR: 1.0,
    FaultKind.NET_DELAY: 1.0,
    FaultKind.NET_GARBAGE: 1.4,
    FaultKind.STORE_FULL: 1.3,
    FaultKind.STORE_CORRUPT: 1.1,
    FaultKind.CONS_DOUBLE_SIGN: 1.2,
    FaultKind.CONS_FALSE_FORK: 1.0,
    FaultKind.BRIDGE_BAD_CLAIM: 1.0,
    FaultKind.RPC_BAD_BATCH: 1.2,
}

_PROD_MODES = frozenset({"prod", "production"})


def refuse_prod_arming(deployment_mode: str) -> None:
    mode = str(deployment_mode or "").strip().lower()
    if mode in _PROD_MODES:
        raise RuntimeError(
            "chaos arming refused: deployment_mode=prod "
            "(TotalChaosEngine is lab/test-only)"
        )


def build_default_chaos_stack(
    *,
    deployment_mode: str = "dev",
    observer: Optional[ChaosObserver] = None,
    rng: Optional[random.Random] = None,
    workers: int = 8,
    coordinated_ratio: float = 0.35,
) -> "TotalChaosEngine":
    refuse_prod_arming(deployment_mode)
    ports: Dict[str, ChaosPort] = {
        "network": NetworkChaosInjector(),
        "storage": StorageChaosInjector(),
        "consensus": ConsensusChaosInjector(),
        "bridge_rpc": BridgeRpcChaosInjector(),
    }
    obs = observer or ChaosObserver()
    return TotalChaosEngine(
        ports,
        obs,
        rng or random.Random(),
        deployment_mode=deployment_mode,
        workers=workers,
        coordinated_ratio=coordinated_ratio,
    )


class TotalChaosEngine:
    """Schedule / arm / fire / stop — random workers + coordinated multi-domain waves."""

    def __init__(
        self,
        ports: Dict[str, ChaosPort],
        observer: ChaosObserverPort,
        rng: random.Random,
        *,
        weights: Optional[Mapping[FaultKind, float]] = None,
        deployment_mode: str = "dev",
        workers: int = 8,
        coordinated_ratio: float = 0.35,
    ) -> None:
        refuse_prod_arming(deployment_mode)
        self.ports = dict(ports)
        self.observer = observer
        self.rng = rng
        self.weights = dict(weights or _DEFAULT_WEIGHTS)
        self.workers = max(1, int(workers))
        self.coordinated_ratio = min(1.0, max(0.0, float(coordinated_ratio)))
        self._stop = False
        self._kind_to_port = self._build_kind_map()
        self._wave_seq = 0

    def _build_kind_map(self) -> Dict[FaultKind, ChaosPort]:
        mapping: Dict[FaultKind, ChaosPort] = {}
        for port in self.ports.values():
            kinds = getattr(port, "KIND_MAP", None) or set()
            for kind in kinds:
                mapping[kind] = port
        return mapping

    def stop(self) -> None:
        self._stop = True

    def _pick_kind(self) -> FaultKind:
        kinds = [k for k in self.weights if k in self._kind_to_port]
        if not kinds:
            raise RuntimeError("no ChaosPort registered for any FaultKind")
        ws = [float(self.weights.get(k, 1.0)) for k in kinds]
        return self.rng.choices(kinds, weights=ws, k=1)[0]

    def _pick_kind_in_family(self, family: FaultFamily) -> Optional[FaultKind]:
        candidates = [k for k in FAMILY_KINDS[family] if k in self._kind_to_port]
        if not candidates:
            return None
        ws = [float(self.weights.get(k, 1.0)) for k in candidates]
        return self.rng.choices(candidates, weights=ws, k=1)[0]

    def _params_for(self, kind: FaultKind, seed: int) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if kind == FaultKind.NET_DELAY:
            params["delay_ms"] = 1 + (abs(seed) % 3)
        elif kind == FaultKind.NET_GARBAGE:
            payloads = (
                b"AB2:\x00\xffgarbage<<<",
                b"not-a-frame",
                b"AB2:" + b"\xff" * 17,
                b"AB2:\x01\x00" + os.urandom(8),
                b"",
                b"\x00" * 64,
                b"AB2:" + bytes(range(32)),
            )
            params["payload"] = payloads[abs(seed) % len(payloads)]
        elif kind == FaultKind.STORE_FULL:
            # Alternate ENOSPC-at-commit vs mid-write ENOSPC token.
            params["token"] = (
                "disk_full" if (abs(seed) % 2 == 0) else "enospc_mid_write"
            )
        elif kind == FaultKind.RPC_BAD_BATCH:
            params["mode"] = ("oversized", "malformed", "bad_params")[abs(seed) % 3]
        return params

    def _next_wave_id(self) -> int:
        self._wave_seq += 1
        return self._wave_seq

    def build_coordinated_wave(self, *, seq: int) -> CoordinatedWave:
        wave_id = self._next_wave_id()
        specs: List[InjectionSpec] = []
        for family in FaultFamily:
            kind = self._pick_kind_in_family(family)
            if kind is None:
                continue
            seed = self.rng.randint(0, 2**31 - 1) ^ (seq * 2654435761) ^ (
                wave_id * 40503
            )
            specs.append(
                InjectionSpec(
                    kind=kind,
                    seed=seed,
                    params=self._params_for(kind, seed),
                    wave_id=wave_id,
                )
            )
        return CoordinatedWave(wave_id=wave_id, specs=tuple(specs))

    def fire_one(
        self, *, seq: int, kind: Optional[FaultKind] = None, wave_id: int = 0
    ) -> InjectionResult:
        if self._stop:
            return InjectionResult(
                kind=FaultKind.NET_TEAR,
                outcome=InjectionOutcome.FAIL_CLOSED.value,
                detail="stopped",
                wave_id=wave_id,
            )
        kind = kind or self._pick_kind()
        seed = self.rng.randint(0, 2**31 - 1) ^ (seq * 2654435761)
        spec = InjectionSpec(
            kind=kind,
            seed=seed,
            params=self._params_for(kind, seed),
            wave_id=wave_id,
        )
        return self._fire_spec(spec)

    def _fire_spec(self, spec: InjectionSpec) -> InjectionResult:
        port = self._kind_to_port.get(spec.kind)
        if port is None:
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail="no_port_for_kind",
                wave_id=spec.wave_id,
            )
        bump = getattr(self.observer, "bump_gauge", None)
        if callable(bump):
            bump("armed_faults", 1)
            bump("queued_injections", 1)
        t0 = time.perf_counter()
        try:
            port.arm(spec)
            result = port.fire(spec)
            elapsed = (time.perf_counter() - t0) * 1000.0
            result = InjectionResult(
                kind=result.kind,
                outcome=result.outcome,
                detail=result.detail,
                wave_id=spec.wave_id,
                elapsed_ms=elapsed,
            )
        except Exception as exc:
            note = getattr(self.observer, "note_uncaught", None)
            if callable(note):
                note(exc)
            result = InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail=f"engine_uncaught:{exc!r}",
                wave_id=spec.wave_id,
                elapsed_ms=(time.perf_counter() - t0) * 1000.0,
            )
        finally:
            try:
                port.disarm()
            except Exception:
                pass
            if callable(bump):
                bump("armed_faults", -1)
                bump("queued_injections", -1)

        leak = self.observer.check_leak_ceilings()
        if leak is not None:
            self.observer.on_result(leak)
            return leak

        self.observer.on_result(result)
        return result

    async def fire_coordinated_wave(self, wave: CoordinatedWave) -> List[InjectionResult]:
        """Fire all specs in a wave concurrently (thread pool for sync ports)."""
        note = getattr(self.observer, "note_coordinated_wave", None)
        if callable(note):
            note()

        async def _one(spec: InjectionSpec) -> InjectionResult:
            bump = getattr(self.observer, "bump_gauge", None)
            if callable(bump):
                bump("active_tasks", 1)
            try:
                return await asyncio.to_thread(self._fire_spec, spec)
            finally:
                if callable(bump):
                    bump("active_tasks", -1)

        return list(await asyncio.gather(*(_one(s) for s in wave.specs)))

    async def run(
        self,
        *,
        duration_sec: float = 120.0,
        injections: int = 500,
        seed: Optional[int] = None,
    ) -> ChaosReport:
        if seed is not None:
            self.rng.seed(int(seed))
        self._stop = False
        duration_sec = float(duration_sec)
        injections = max(0, int(injections))
        deadline = time.monotonic() + duration_sec
        seq = 0
        lock = asyncio.Lock()

        # Coverage floor: every FaultKind once.
        coverage_kinds: Sequence[FaultKind] = tuple(
            sorted(self._kind_to_port, key=lambda k: k.value)
        )
        for kind in coverage_kinds:
            if seq >= injections or time.monotonic() >= deadline or self._stop:
                break
            my = seq
            seq += 1
            await asyncio.to_thread(self.fire_one, seq=my, kind=kind)

        # At least one coordinated multi-domain wave early (within budget).
        if seq < injections and time.monotonic() < deadline and not self._stop:
            wave = self.build_coordinated_wave(seq=seq)
            budget = min(len(wave.specs), injections - seq)
            if budget > 0:
                trimmed = CoordinatedWave(
                    wave_id=wave.wave_id, specs=tuple(wave.specs)[:budget]
                )
                results = await self.fire_coordinated_wave(trimmed)
                seq += len(results)

        async def worker() -> None:
            nonlocal seq
            while True:
                if self._stop or time.monotonic() >= deadline:
                    return
                async with lock:
                    if seq >= injections:
                        return
                    use_wave = (
                        self.coordinated_ratio > 0
                        and self.rng.random() < self.coordinated_ratio
                        and (injections - seq) >= 2
                    )
                    if use_wave:
                        wave = self.build_coordinated_wave(seq=seq)
                        budget = min(len(wave.specs), injections - seq)
                        specs = list(wave.specs)[:budget]
                        wave = CoordinatedWave(wave_id=wave.wave_id, specs=tuple(specs))
                        seq += len(specs)
                        my_wave = wave
                        my_seq = None
                    else:
                        my_seq = seq
                        seq += 1
                        my_wave = None
                    bump = getattr(self.observer, "bump_gauge", None)
                    if callable(bump) and my_wave is None:
                        bump("active_tasks", 1)
                try:
                    if my_wave is not None:
                        await self.fire_coordinated_wave(my_wave)
                    else:
                        await asyncio.to_thread(self.fire_one, seq=int(my_seq or 0))
                finally:
                    if my_wave is None:
                        bump = getattr(self.observer, "bump_gauge", None)
                        if callable(bump):
                            bump("active_tasks", -1)

        tasks = [asyncio.create_task(worker()) for _ in range(self.workers)]
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks),
                timeout=max(duration_sec + 30.0, 60.0),
            )
        except asyncio.TimeoutError:
            self._stop = True
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.observer.on_result(
                InjectionResult(
                    kind=FaultKind.NET_TEAR,
                    outcome=InjectionOutcome.PANIC.value,
                    detail="engine_timeout",
                )
            )

        # Final leak / deadlock ceiling check.
        leak = self.observer.check_leak_ceilings()
        if leak is not None:
            self.observer.on_result(leak)

        return self.observer.report()


def chaos_env_knobs() -> tuple[float, int]:
    """Read CHAOS_DURATION_SEC / CHAOS_INJECTIONS (defaults 120 / 500)."""
    duration = float(os.environ.get("CHAOS_DURATION_SEC", "120") or 120)
    injections = int(os.environ.get("CHAOS_INJECTIONS", "500") or 500)
    return duration, injections
