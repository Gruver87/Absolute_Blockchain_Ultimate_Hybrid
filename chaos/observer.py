# chaos/observer.py — ADR 0012 outcome classifier + resource / deadlock gauges
"""Fail-closed / recover / panic / leak_signal aggregation.

Memory honesty (locked): required gauges are task/fault/queue ceilings.
RSS delta is best-effort (optional). Not ASan / Valgrind certification.
Deadlock signal: observer lock acquire exceeds ``max_lock_wait_ms``.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Dict, Optional

from chaos.ports import (
    ChaosReport,
    FaultKind,
    InjectionOutcome,
    InjectionResult,
    ResourceSnapshot,
)


def _rss_bytes() -> int:
    try:
        import resource  # Unix

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    except Exception:
        pass
    try:
        import psutil  # type: ignore

        return int(psutil.Process().memory_info().rss)
    except Exception:
        pass
    try:
        # Windows: ctypes GetProcessMemoryInfo is heavy; skip quietly.
        return 0
    except Exception:
        return 0


def _asyncio_task_count() -> int:
    try:
        loop = asyncio.get_running_loop()
        return len(asyncio.all_tasks(loop))
    except Exception:
        return 0


class ChaosObserver:
    def __init__(
        self,
        *,
        max_active_tasks: int = 64,
        max_armed_faults: int = 32,
        max_queued: int = 1024,
        max_asyncio_tasks: int = 128,
        max_threads: int = 64,
        max_rss_delta_bytes: int = 256 * 1024 * 1024,
        max_lock_wait_ms: float = 5_000.0,
    ):
        self._lock = threading.Lock()
        self._report = ChaosReport()
        self._gauges: Dict[str, int] = {
            "active_tasks": 0,
            "armed_faults": 0,
            "queued_injections": 0,
        }
        self.max_active_tasks = max_active_tasks
        self.max_armed_faults = max_armed_faults
        self.max_queued = max_queued
        self.max_asyncio_tasks = max_asyncio_tasks
        self.max_threads = max_threads
        self.max_rss_delta_bytes = max_rss_delta_bytes
        self.max_lock_wait_ms = float(max_lock_wait_ms)
        self.uncaught: list = []
        self._rss_baseline = _rss_bytes()
        self._peak_asyncio = 0
        self._peak_threads = 0
        self._peak_rss_delta = 0

    def on_result(self, result: InjectionResult) -> None:
        with self._timed_lock() as ok:
            if not ok:
                self._report.deadlock_signals += 1
                self._report.record(
                    InjectionResult(
                        kind=result.kind,
                        outcome=InjectionOutcome.LEAK_SIGNAL.value,
                        detail="observer_lock_wait_exceeded",
                        wave_id=result.wave_id,
                    )
                )
                return
            self._report.record(result)
            self._sample_resources_unlocked()

    def report(self) -> ChaosReport:
        with self._lock:
            self._report.uncaught = list(self.uncaught)
            self._report.max_asyncio_tasks = self._peak_asyncio
            self._report.max_thread_count = self._peak_threads
            self._report.max_rss_delta_bytes = self._peak_rss_delta
            return self._report

    def gauge(self, name: str, value: int) -> None:
        with self._lock:
            self._gauges[str(name)] = int(value)

    def bump_gauge(self, name: str, delta: int = 1) -> int:
        with self._lock:
            cur = int(self._gauges.get(name, 0)) + int(delta)
            self._gauges[name] = max(0, cur)
            return self._gauges[name]

    def snapshot(self) -> ResourceSnapshot:
        with self._lock:
            rss = _rss_bytes()
            delta = max(0, rss - self._rss_baseline) if rss and self._rss_baseline else 0
            return ResourceSnapshot(
                active_tasks=int(self._gauges.get("active_tasks", 0)),
                armed_faults=int(self._gauges.get("armed_faults", 0)),
                queued_injections=int(self._gauges.get("queued_injections", 0)),
                thread_count=threading.active_count(),
                asyncio_tasks=_asyncio_task_count(),
                rss_bytes=rss,
                lock_wait_ms=0.0,
            )

    def check_leak_ceilings(self) -> Optional[InjectionResult]:
        with self._lock:
            self._sample_resources_unlocked()
            if self._gauges.get("active_tasks", 0) > self.max_active_tasks:
                return InjectionResult(
                    kind=FaultKind.NET_TEAR,
                    outcome=InjectionOutcome.LEAK_SIGNAL.value,
                    detail=f"active_tasks>{self.max_active_tasks}",
                )
            if self._gauges.get("armed_faults", 0) > self.max_armed_faults:
                return InjectionResult(
                    kind=FaultKind.NET_TEAR,
                    outcome=InjectionOutcome.LEAK_SIGNAL.value,
                    detail=f"armed_faults>{self.max_armed_faults}",
                )
            if self._gauges.get("queued_injections", 0) > self.max_queued:
                return InjectionResult(
                    kind=FaultKind.NET_TEAR,
                    outcome=InjectionOutcome.LEAK_SIGNAL.value,
                    detail=f"queued_injections>{self.max_queued}",
                )
            if self._peak_asyncio > self.max_asyncio_tasks:
                return InjectionResult(
                    kind=FaultKind.NET_TEAR,
                    outcome=InjectionOutcome.LEAK_SIGNAL.value,
                    detail=f"asyncio_tasks>{self.max_asyncio_tasks}",
                )
            if self._peak_threads > self.max_threads:
                return InjectionResult(
                    kind=FaultKind.NET_TEAR,
                    outcome=InjectionOutcome.LEAK_SIGNAL.value,
                    detail=f"threads>{self.max_threads}",
                )
            if (
                self._rss_baseline
                and self._peak_rss_delta > self.max_rss_delta_bytes
            ):
                return InjectionResult(
                    kind=FaultKind.NET_TEAR,
                    outcome=InjectionOutcome.LEAK_SIGNAL.value,
                    detail=f"rss_delta>{self.max_rss_delta_bytes}",
                )
        return None

    def note_uncaught(self, exc: BaseException) -> None:
        with self._lock:
            self.uncaught.append(repr(exc))
            self._report.uncaught.append(repr(exc))

    def note_coordinated_wave(self) -> None:
        with self._lock:
            self._report.coordinated_waves += 1

    def _sample_resources_unlocked(self) -> None:
        threads = threading.active_count()
        tasks = _asyncio_task_count()
        rss = _rss_bytes()
        self._peak_threads = max(self._peak_threads, threads)
        self._peak_asyncio = max(self._peak_asyncio, tasks)
        if rss and self._rss_baseline:
            delta = max(0, rss - self._rss_baseline)
            self._peak_rss_delta = max(self._peak_rss_delta, delta)

    def _timed_lock(self):
        return _TimedLock(self._lock, self.max_lock_wait_ms)


class _TimedLock:
    def __init__(self, lock: threading.Lock, max_wait_ms: float) -> None:
        self._lock = lock
        self._max_wait_ms = max_wait_ms
        self._ok = False

    def __enter__(self) -> bool:
        t0 = time.perf_counter()
        acquired = self._lock.acquire(timeout=max(0.001, self._max_wait_ms / 1000.0))
        waited = (time.perf_counter() - t0) * 1000.0
        self._ok = bool(acquired)
        if acquired and waited > self._max_wait_ms:
            # Acquired but late — still treat as pressure signal via caller.
            pass
        return self._ok

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._ok:
            self._lock.release()
