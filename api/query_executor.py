# api/query_executor.py — ADR 0011 bounded heavy-query pool
"""Thread pool + timeout for eth_getLogs / full-tx block reads."""

from __future__ import annotations

import concurrent.futures
from typing import Any, Callable, Optional, TypeVar

from api.ports import QueryTimeoutError

T = TypeVar("T")


class QueryExecutor:
    def __init__(self, *, workers: int = 2, default_timeout_ms: int = 5000):
        self.default_timeout_ms = max(1, int(default_timeout_ms or 5000))
        n = max(1, int(workers or 2))
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=n, thread_name_prefix="rpc-query"
        )

    def submit(
        self,
        fn: Callable[[], T],
        *,
        timeout_ms: Optional[int] = None,
    ) -> T:
        timeout = (timeout_ms if timeout_ms is not None else self.default_timeout_ms) / 1000.0
        fut = self._pool.submit(fn)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            fut.cancel()
            raise QueryTimeoutError("query_timeout") from exc

    def shutdown(self, wait: bool = False) -> None:
        self._pool.shutdown(wait=wait, cancel_futures=True)
