#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Распределённый rate limit через Redis (multi-node / K8s)."""

import time
from typing import Tuple, Optional


class RedisRateLimiter:
    """Фиксированное окно: INCR + EXPIRE на ключ клиента."""

    def __init__(
        self,
        redis_url: str,
        requests_per_minute: int = 120,
        window_seconds: int = 60,
        key_prefix: str = "abs:rl",
        fail_closed: bool = True,
    ):
        import redis

        self.client = redis.from_url(redis_url, decode_responses=True)
        self.client.ping()
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self.fail_closed = bool(fail_closed)

    def _bucket_key(self, client_id: str) -> str:
        window_id = int(time.time()) // self.window_seconds
        return f"{self.key_prefix}:{client_id}:{window_id}"

    def allow_request(self, client_id: str) -> Tuple[bool, int]:
        key = self._bucket_key(client_id)
        try:
            count = self.client.incr(key)
            if count == 1:
                self.client.expire(key, self.window_seconds + 1)
            remaining = max(0, self.requests_per_minute - count)
            return count <= self.requests_per_minute, remaining
        except Exception:
            if self.fail_closed:
                return False, 0
            return True, self.requests_per_minute

    def reset(self, client_id: str) -> None:
        try:
            pattern = f"{self.key_prefix}:{client_id}:*"
            for key in self.client.scan_iter(match=pattern, count=50):
                self.client.delete(key)
        except Exception as exc:
            # Never silent: ops need to see denylist/reset failures.
            print(f"[RedisRateLimiter] reset failed for {client_id}: {exc}")


def try_create_redis_limiter(
    redis_url: str,
    requests_per_minute: int = 120,
    window_seconds: int = 60,
    fail_closed: bool = True,
) -> Optional[RedisRateLimiter]:
    if not redis_url:
        return None
    try:
        return RedisRateLimiter(
            redis_url,
            requests_per_minute,
            window_seconds,
            fail_closed=fail_closed,
        )
    except Exception:
        return None
