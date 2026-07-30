# chaos/ports.py — ADR 0012 Chaos Injection surfaces
"""Fault kinds, injection DTOs, ChaosPort / ChaosObserverPort protocols.

Lab/test-only. Production ``main.py`` / NodeOrchestrator must never import this
module for arming. Ports live under ``chaos/`` (package); ``tests/chaos/ports.py``
re-exports the same symbols for harness convenience.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Sequence, runtime_checkable


class FaultKind(str, Enum):
    NET_TEAR = "net_tear"
    NET_DELAY = "net_delay"
    NET_GARBAGE = "net_garbage"
    STORE_FULL = "store_full"
    STORE_CORRUPT = "store_corrupt"
    CONS_DOUBLE_SIGN = "cons_double_sign"
    CONS_FALSE_FORK = "cons_false_fork"
    BRIDGE_BAD_CLAIM = "bridge_bad_claim"
    RPC_BAD_BATCH = "rpc_bad_batch"


class InjectionOutcome(str, Enum):
    FAIL_CLOSED = "FAIL_CLOSED"
    RECOVERED = "RECOVERED"
    PANIC = "PANIC"
    LEAK_SIGNAL = "LEAK_SIGNAL"


class FaultFamily(str, Enum):
    """Domain families for coordinated multi-port waves."""

    NETWORK = "network"
    STORAGE = "storage"
    CONSENSUS = "consensus"
    BRIDGE_RPC = "bridge_rpc"


FAMILY_KINDS: Dict[FaultFamily, Sequence[FaultKind]] = {
    FaultFamily.NETWORK: (
        FaultKind.NET_TEAR,
        FaultKind.NET_DELAY,
        FaultKind.NET_GARBAGE,
    ),
    FaultFamily.STORAGE: (
        FaultKind.STORE_FULL,
        FaultKind.STORE_CORRUPT,
    ),
    FaultFamily.CONSENSUS: (
        FaultKind.CONS_DOUBLE_SIGN,
        FaultKind.CONS_FALSE_FORK,
    ),
    FaultFamily.BRIDGE_RPC: (
        FaultKind.BRIDGE_BAD_CLAIM,
        FaultKind.RPC_BAD_BATCH,
    ),
}


@dataclass(frozen=True)
class InjectionSpec:
    kind: FaultKind
    seed: int
    params: Dict[str, Any] = field(default_factory=dict)
    wave_id: int = 0


@dataclass(frozen=True)
class InjectionResult:
    kind: FaultKind
    outcome: str
    detail: str = ""
    wave_id: int = 0
    elapsed_ms: float = 0.0


@dataclass(frozen=True)
class CoordinatedWave:
    """One parallel strike across multiple FaultFamilies (same wave_id)."""

    wave_id: int
    specs: Sequence[InjectionSpec]


@dataclass(frozen=True)
class ResourceSnapshot:
    """Bounded resource gauges — honesty substitute for ASan/Valgrind."""

    active_tasks: int = 0
    armed_faults: int = 0
    queued_injections: int = 0
    thread_count: int = 0
    asyncio_tasks: int = 0
    rss_bytes: int = 0
    lock_wait_ms: float = 0.0


@dataclass
class ChaosReport:
    total: int = 0
    fail_closed: int = 0
    recovered: int = 0
    panic_count: int = 0
    leak_signal_count: int = 0
    coordinated_waves: int = 0
    by_kind: Dict[str, int] = field(default_factory=dict)
    details: list = field(default_factory=list)
    max_rss_delta_bytes: int = 0
    max_asyncio_tasks: int = 0
    max_thread_count: int = 0
    deadlock_signals: int = 0
    uncaught: List[str] = field(default_factory=list)

    def record(self, result: InjectionResult) -> None:
        self.total += 1
        key = result.kind.value if isinstance(result.kind, FaultKind) else str(result.kind)
        self.by_kind[key] = int(self.by_kind.get(key, 0)) + 1
        if result.outcome == InjectionOutcome.FAIL_CLOSED.value:
            self.fail_closed += 1
        elif result.outcome == InjectionOutcome.RECOVERED.value:
            self.recovered += 1
        elif result.outcome == InjectionOutcome.PANIC.value:
            self.panic_count += 1
        elif result.outcome == InjectionOutcome.LEAK_SIGNAL.value:
            self.leak_signal_count += 1
        if len(self.details) < 128:
            self.details.append(
                {
                    "kind": key,
                    "outcome": result.outcome,
                    "detail": result.detail,
                    "wave_id": result.wave_id,
                    "elapsed_ms": result.elapsed_ms,
                }
            )


@runtime_checkable
class ChaosPort(Protocol):
    def arm(self, spec: InjectionSpec) -> None:
        ...

    def fire(self, spec: InjectionSpec) -> InjectionResult:
        ...

    def disarm(self) -> None:
        ...


@runtime_checkable
class ChaosObserverPort(Protocol):
    def on_result(self, result: InjectionResult) -> None:
        ...

    def report(self) -> ChaosReport:
        ...

    def gauge(self, name: str, value: int) -> None:
        ...

    def check_leak_ceilings(self) -> Optional[InjectionResult]:
        ...

    def snapshot(self) -> ResourceSnapshot:
        ...
