#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serial chain apply queue — mine and P2P import share one worker.

Closes the create_block → add_block race window against concurrent import_block
by serializing all tip mutations on a single thread with a bounded queue.

v1.3.66: enqueue deadlines — not-yet-started jobs expire instead of applying
after the caller's Future.result timeout.

v1.3.73: priority lanes — REORG > FORGE > ADD > IMPORT so sync floods cannot
starve mining / fork resolution (FIFO within the same priority).
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


class ApplyOpKind(Enum):
    IMPORT = auto()
    ADD = auto()
    FORGE_AND_APPLY = auto()
    REORG_AND_IMPORT = auto()
    REORG = auto()
    STOP = auto()


# Lower number = higher priority (queue.PriorityQueue).
_APPLY_PRIORITY: Dict[ApplyOpKind, int] = {
    ApplyOpKind.STOP: 0,
    ApplyOpKind.REORG: 1,
    ApplyOpKind.REORG_AND_IMPORT: 1,
    ApplyOpKind.FORGE_AND_APPLY: 2,
    ApplyOpKind.ADD: 3,
    ApplyOpKind.IMPORT: 4,
}


@dataclass
class _Job:
    kind: ApplyOpKind
    future: Future
    payload: Any = None
    deadline_monotonic: float = 0.0
    enqueued_at: float = field(default_factory=time.monotonic)


@dataclass(order=True)
class _PriItem:
    """PriorityQueue entry: priority, then FIFO seq for equal lanes."""

    priority: int
    seq: int
    job: _Job = field(compare=False)


class ChainApplyQueue:
    """Single-worker serial apply for Blockchain tip mutations."""

    def __init__(
        self,
        blockchain: Any,
        *,
        maxsize: int = 64,
        timeout_sec: float = 120.0,
        name: str = "ChainApply",
    ) -> None:
        self.blockchain = blockchain
        self.maxsize = max(1, int(maxsize))
        self.timeout_sec = float(timeout_sec)
        # v1.3.73: PriorityQueue (not FIFO Queue)
        self._q: queue.PriorityQueue = queue.PriorityQueue(maxsize=self.maxsize)
        self._seq = 0
        self._seq_lock = threading.Lock()
        self._running = True
        self.reject_total = 0
        self.completed_total = 0
        self.expired_total = 0
        self.timeout_total = 0
        self.error_total = 0
        self.wait_seconds_total = 0.0
        self.exec_seconds_total = 0.0
        self._depth_lock = threading.Lock()
        self._worker = threading.Thread(target=self._run, name=name, daemon=True)
        self._worker.start()

    @property
    def depth(self) -> int:
        return int(self._q.qsize())

    def stats(self) -> Dict[str, Any]:
        return {
            "queue_depth": self.depth,
            "reject_total": int(self.reject_total),
            "completed_total": int(self.completed_total),
            "expired_total": int(self.expired_total),
            "timeout_total": int(self.timeout_total),
            "error_total": int(self.error_total),
            "wait_seconds_total": float(self.wait_seconds_total),
            "exec_seconds_total": float(self.exec_seconds_total),
            "timeout_sec": float(self.timeout_sec),
            "maxsize": int(self.maxsize),
            "priority_lanes": True,
            "priority_order": "reorg>forge>add>import",
        }

    def stop(self, join_timeout: float = 5.0) -> None:
        self._running = False
        try:
            self._put_job(_Job(ApplyOpKind.STOP, Future()))
        except queue.Full:
            pass
        self._worker.join(timeout=join_timeout)

    def _put_job(self, job: _Job) -> None:
        with self._seq_lock:
            self._seq += 1
            seq = self._seq
        pri = int(_APPLY_PRIORITY.get(job.kind, 9))
        self._q.put_nowait(_PriItem(priority=pri, seq=seq, job=job))

    def _enqueue(self, kind: ApplyOpKind, payload: Any = None) -> Future:
        fut: Future = Future()
        now = time.monotonic()
        job = _Job(
            kind=kind,
            future=fut,
            payload=payload,
            deadline_monotonic=now + self.timeout_sec,
            enqueued_at=now,
        )
        try:
            self._put_job(job)
        except queue.Full:
            self.reject_total += 1
            fut.set_result(("rejected", None))
        return fut

    def _result_or_timeout(self, fut: Future) -> Any:
        try:
            return fut.result(timeout=self.timeout_sec)
        except Exception as exc:
            self.timeout_total += 1
            return ("error", exc)

    def submit_import(self, block_data: Dict) -> bool:
        started = time.perf_counter()
        fut = self._enqueue(ApplyOpKind.IMPORT, block_data)
        out = self._result_or_timeout(fut)
        self.wait_seconds_total += time.perf_counter() - started
        if isinstance(out, tuple) and out and out[0] in ("rejected", "error", "expired"):
            return False
        return bool(out)

    def submit_add(self, block: Any) -> bool:
        started = time.perf_counter()
        fut = self._enqueue(ApplyOpKind.ADD, block)
        out = self._result_or_timeout(fut)
        self.wait_seconds_total += time.perf_counter() - started
        if isinstance(out, tuple) and out and out[0] in ("rejected", "error", "expired"):
            return False
        return bool(out)

    def submit_forge_and_apply(
        self,
        txs: List[Any],
        proposer: str,
        sign_fn: Optional[Callable[[Any], None]] = None,
    ) -> Tuple[bool, Any]:
        started = time.perf_counter()
        fut = self._enqueue(ApplyOpKind.FORGE_AND_APPLY, (txs, proposer, sign_fn))
        out = self._result_or_timeout(fut)
        self.wait_seconds_total += time.perf_counter() - started
        if isinstance(out, tuple) and out and out[0] in ("rejected", "error", "expired"):
            return False, None
        if not isinstance(out, tuple) or len(out) != 2:
            return False, None
        ok, block = out
        return bool(ok), block

    def submit_reorg_and_import(self, rollback_to: int, peer_block: Dict) -> bool:
        started = time.perf_counter()
        fut = self._enqueue(ApplyOpKind.REORG_AND_IMPORT, (int(rollback_to), peer_block))
        out = self._result_or_timeout(fut)
        self.wait_seconds_total += time.perf_counter() - started
        if isinstance(out, tuple) and out and out[0] in ("rejected", "error", "expired"):
            return False
        return bool(out)

    def submit_reorg(self, rollback_to: int) -> bool:
        started = time.perf_counter()
        fut = self._enqueue(ApplyOpKind.REORG, int(rollback_to))
        out = self._result_or_timeout(fut)
        self.wait_seconds_total += time.perf_counter() - started
        if isinstance(out, tuple) and out and out[0] in ("rejected", "error", "expired"):
            return False
        return bool(out)

    async def submit_import_async(self, block_data: Dict) -> bool:
        return await asyncio.to_thread(self.submit_import, block_data)

    async def submit_forge_and_apply_async(
        self,
        txs: List[Any],
        proposer: str,
        sign_fn: Optional[Callable[[Any], None]] = None,
    ) -> Tuple[bool, Any]:
        return await asyncio.to_thread(self.submit_forge_and_apply, txs, proposer, sign_fn)

    async def submit_reorg_and_import_async(
        self, rollback_to: int, peer_block: Dict
    ) -> bool:
        return await asyncio.to_thread(
            self.submit_reorg_and_import, int(rollback_to), peer_block
        )

    async def submit_reorg_async(self, rollback_to: int) -> bool:
        return await asyncio.to_thread(self.submit_reorg, int(rollback_to))

    def _run(self) -> None:
        while self._running:
            try:
                item: _PriItem = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            job = item.job
            if job.kind is ApplyOpKind.STOP:
                job.future.set_result(True)
                break
            # v1.3.66: skip not-yet-started jobs past deadline.
            if job.deadline_monotonic and time.monotonic() > job.deadline_monotonic:
                self.expired_total += 1
                if not job.future.done():
                    job.future.set_result(("expired", None))
                continue
            try:
                t0 = time.perf_counter()
                result = self._dispatch(job)
                self.exec_seconds_total += time.perf_counter() - t0
                if not job.future.done():
                    job.future.set_result(result)
                self.completed_total += 1
            except Exception as exc:
                self.error_total += 1
                if not job.future.done():
                    job.future.set_exception(exc)

    def _dispatch(self, job: _Job) -> Any:
        bc = self.blockchain
        if job.kind is ApplyOpKind.IMPORT:
            if hasattr(bc, "import_block"):
                return bool(bc.import_block(job.payload))
            return False
        if job.kind is ApplyOpKind.ADD:
            return bool(bc.add_block(job.payload))
        if job.kind is ApplyOpKind.FORGE_AND_APPLY:
            txs, proposer, sign_fn = job.payload
            block = bc.create_block(list(txs or []), str(proposer))
            if sign_fn is not None:
                sign_fn(block)
            ok = bool(bc.add_block(block))
            return ok, block
        if job.kind is ApplyOpKind.REORG_AND_IMPORT:
            rollback_to, peer_block = job.payload
            if not bc.reorg_to_ancestor(int(rollback_to)):
                return False
            return bool(bc.import_block(peer_block))
        if job.kind is ApplyOpKind.REORG:
            return bool(bc.reorg_to_ancestor(int(job.payload)))
        raise RuntimeError(f"unknown apply op: {job.kind}")
