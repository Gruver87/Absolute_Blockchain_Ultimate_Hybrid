#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serial chain apply queue — mine and P2P import share one worker.

Closes the create_block → add_block race window against concurrent import_block
by serializing all tip mutations on a single thread with a bounded queue.
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


class ApplyOpKind(Enum):
    IMPORT = auto()
    ADD = auto()
    FORGE_AND_APPLY = auto()
    REORG_AND_IMPORT = auto()
    REORG = auto()
    STOP = auto()


@dataclass
class _Job:
    kind: ApplyOpKind
    future: Future
    payload: Any = None


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
        self._q: queue.Queue = queue.Queue(maxsize=self.maxsize)
        self._running = True
        self.reject_total = 0
        self.completed_total = 0
        self.wait_seconds_total = 0.0
        self._depth_lock = threading.Lock()
        self._worker = threading.Thread(target=self._run, name=name, daemon=True)
        self._worker.start()

    @property
    def depth(self) -> int:
        return int(self._q.qsize())

    def stop(self, join_timeout: float = 5.0) -> None:
        self._running = False
        try:
            self._q.put_nowait(_Job(ApplyOpKind.STOP, Future()))
        except queue.Full:
            pass
        self._worker.join(timeout=join_timeout)

    def _enqueue(self, kind: ApplyOpKind, payload: Any = None) -> Future:
        fut: Future = Future()
        job = _Job(kind=kind, future=fut, payload=payload)
        try:
            self._q.put_nowait(job)
        except queue.Full:
            self.reject_total += 1
            fut.set_result(("rejected", None))
        return fut

    def _result_or_timeout(self, fut: Future) -> Any:
        try:
            return fut.result(timeout=self.timeout_sec)
        except Exception as exc:
            return ("error", exc)

    def submit_import(self, block_data: Dict) -> bool:
        started = time.perf_counter()
        fut = self._enqueue(ApplyOpKind.IMPORT, block_data)
        out = self._result_or_timeout(fut)
        self.wait_seconds_total += time.perf_counter() - started
        if isinstance(out, tuple) and out and out[0] == "rejected":
            return False
        if isinstance(out, tuple) and out and out[0] == "error":
            return False
        return bool(out)

    def submit_add(self, block: Any) -> bool:
        started = time.perf_counter()
        fut = self._enqueue(ApplyOpKind.ADD, block)
        out = self._result_or_timeout(fut)
        self.wait_seconds_total += time.perf_counter() - started
        if isinstance(out, tuple) and out and out[0] in ("rejected", "error"):
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
        if isinstance(out, tuple) and out and out[0] == "rejected":
            return False, None
        if isinstance(out, tuple) and out and out[0] == "error":
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
        if isinstance(out, tuple) and out and out[0] in ("rejected", "error"):
            return False
        return bool(out)

    def submit_reorg(self, rollback_to: int) -> bool:
        started = time.perf_counter()
        fut = self._enqueue(ApplyOpKind.REORG, int(rollback_to))
        out = self._result_or_timeout(fut)
        self.wait_seconds_total += time.perf_counter() - started
        if isinstance(out, tuple) and out and out[0] in ("rejected", "error"):
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
                job: _Job = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if job.kind is ApplyOpKind.STOP:
                job.future.set_result(True)
                break
            try:
                result = self._dispatch(job)
                if not job.future.done():
                    job.future.set_result(result)
                self.completed_total += 1
            except Exception as exc:
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
