#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rate Limiter - защита от DDoS и спама"""

import time
from collections import defaultdict
from typing import Optional, Tuple

class RateLimiter:
    """Токен-бакет алгоритм"""
    
    def __init__(self, requests_per_minute: int = 100, window_seconds: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.requests: defaultdict = defaultdict(list)
    
    def allow_request(self, client_id: str) -> Tuple[bool, int]:
        """
        Проверяет, можно ли выполнить запрос
        Возвращает: (разрешено, осталось_запросов)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Очищаем старые запросы
        self.requests[client_id] = [
            t for t in self.requests[client_id] 
            if t > window_start
        ]
        
        remaining = self.requests_per_minute - len(self.requests[client_id])
        
        if len(self.requests[client_id]) < self.requests_per_minute:
            self.requests[client_id].append(now)
            return True, remaining - 1
        
        return False, 0
    
    def reset(self, client_id: str):
        """Сбросить лимит для клиента"""
        if client_id in self.requests:
            del self.requests[client_id]

# Глобальный экземпляр (in-memory fallback)
rate_limiter = RateLimiter()


def create_rate_limiter(
    *,
    redis_url: str = "",
    redis_enabled: bool = False,
    requests_per_minute: int = 120,
    window_seconds: int = 60,
    fail_closed: bool = False,
):
    """In-memory или Redis.

    When redis_enabled=True and fail_closed=True, returns None if Redis is
    unavailable (no silent memory fallback). Dev may fall back to memory.
    """
    if redis_enabled:
        if not redis_url:
            if fail_closed:
                return None
            return RateLimiter(
                requests_per_minute=requests_per_minute, window_seconds=window_seconds
            )
        from middleware.redis_rate_limit import try_create_redis_limiter

        rl = try_create_redis_limiter(
            redis_url,
            requests_per_minute,
            window_seconds,
            fail_closed=fail_closed,
        )
        if rl is not None:
            return rl
        if fail_closed:
            return None
    return RateLimiter(requests_per_minute=requests_per_minute, window_seconds=window_seconds)


def rate_limiter_backend_name(limiter: Optional[object]) -> str:
    if limiter is None:
        return "none"
    mod = type(limiter).__module__
    name = type(limiter).__name__
    if "redis" in mod.lower() or "Redis" in name:
        return "redis"
    return "memory"
