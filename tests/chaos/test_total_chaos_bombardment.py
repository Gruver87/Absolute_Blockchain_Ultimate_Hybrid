# tests/chaos/test_total_chaos_bombardment.py — ADR 0012 TotalChaosEngine DoD
"""Parallel + coordinated fault bombardment.

DoD:
  - panic_count == 0, leak_signal_count == 0, deadlock_signals == 0
  - fail_closed + recovered == total
  - every FaultKind covered
  - coordinated waves fired
  - resource gauges bounded (tasks / threads / optional RSS)
  - no uncaught exceptions at Python injector seam (Rust FFI not entered for garbage)
"""

from __future__ import annotations

import os
import threading

import pytest

from chaos.engine import TotalChaosEngine, build_default_chaos_stack, refuse_prod_arming
from chaos.observer import ChaosObserver
from chaos.ports import FaultKind


def test_refuse_prod_arming():
    with pytest.raises(RuntimeError, match="prod"):
        refuse_prod_arming("prod")
    with pytest.raises(RuntimeError, match="prod"):
        build_default_chaos_stack(deployment_mode="production")


def test_coordinated_wave_covers_families():
    engine = build_default_chaos_stack(deployment_mode="dev", rng=__import__("random").Random(7))
    wave = engine.build_coordinated_wave(seq=1)
    assert len(wave.specs) >= 4
    kinds = {s.kind for s in wave.specs}
    assert FaultKind.NET_TEAR in kinds or FaultKind.NET_DELAY in kinds or FaultKind.NET_GARBAGE in kinds
    assert FaultKind.STORE_FULL in kinds or FaultKind.STORE_CORRUPT in kinds
    assert FaultKind.CONS_DOUBLE_SIGN in kinds or FaultKind.CONS_FALSE_FORK in kinds
    assert FaultKind.BRIDGE_BAD_CLAIM in kinds or FaultKind.RPC_BAD_BATCH in kinds


def _assert_report_healthy(report, *, injections: int) -> None:
    assert report.panic_count == 0, report.details
    assert report.leak_signal_count == 0, report.details
    assert report.deadlock_signals == 0, report.details
    assert not report.uncaught, report.uncaught
    assert report.fail_closed + report.recovered == report.total
    assert report.total == injections
    for kind in FaultKind:
        assert report.by_kind.get(kind.value, 0) >= 1, f"missing coverage for {kind}"
    assert report.coordinated_waves >= 1, "expected ≥1 coordinated multi-domain wave"
    # Bounded Python-side gauges (honesty: not Valgrind).
    assert report.max_asyncio_tasks <= 128, report.max_asyncio_tasks
    assert report.max_thread_count <= 64, report.max_thread_count


@pytest.mark.chaos
@pytest.mark.chaos_smoke
@pytest.mark.asyncio
async def test_total_chaos_bombardment_smoke():
    """CI-safe subset — env overrides welcome; defaults stay small."""
    duration = float(os.environ.get("CHAOS_DURATION_SEC", "15") or 15)
    injections = int(os.environ.get("CHAOS_INJECTIONS", "36") or 36)
    if os.environ.get("CHAOS_FULL") != "1":
        duration = min(duration, 15.0)
        injections = min(injections, 36)

    observer = ChaosObserver()
    engine = build_default_chaos_stack(
        deployment_mode="dev",
        observer=observer,
        workers=6,
        coordinated_ratio=0.4,
    )
    assert isinstance(engine, TotalChaosEngine)
    threads_before = threading.active_count()
    report = await engine.run(duration_sec=duration, injections=injections, seed=42)
    snap = observer.snapshot()

    _assert_report_healthy(report, injections=injections)
    assert snap.armed_faults == 0
    assert snap.queued_injections == 0
    assert snap.active_tasks == 0
    # Thread pool workers may linger briefly; industrial ceiling is max_threads.
    assert threading.active_count() <= max(threads_before + 24, 32)


@pytest.mark.chaos
@pytest.mark.chaos_full
@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("CHAOS_FULL") != "1",
    reason="full 2min bombardment: set CHAOS_FULL=1 (see docs/COMMANDS_REFERENCE.md)",
)
async def test_total_chaos_bombardment_2min():
    """≥500 aggressive runtime faults / ≤120s — panic & leak_signal fail hard."""
    duration = float(os.environ.get("CHAOS_DURATION_SEC", "120") or 120)
    injections = int(os.environ.get("CHAOS_INJECTIONS", "500") or 500)

    observer = ChaosObserver(
        max_active_tasks=64,
        max_armed_faults=32,
        max_queued=1024,
        max_asyncio_tasks=128,
        max_threads=64,
        max_rss_delta_bytes=512 * 1024 * 1024,
    )
    engine = build_default_chaos_stack(
        deployment_mode="dev",
        observer=observer,
        workers=8,
        coordinated_ratio=0.35,
    )
    threads_before = threading.active_count()
    report = await engine.run(duration_sec=duration, injections=injections, seed=777)
    snap = observer.snapshot()

    _assert_report_healthy(report, injections=injections)
    assert report.total >= 500
    assert snap.armed_faults == 0
    assert snap.queued_injections == 0
    assert snap.active_tasks == 0
    # asyncio.to_thread leaves default executor workers; bound by observer max_threads.
    assert threading.active_count() <= max(threads_before + 24, 32)
    assert report.max_thread_count <= 64
    # Coordinated pressure must have exercised multi-family gather.
    assert report.coordinated_waves >= 5, report.coordinated_waves
