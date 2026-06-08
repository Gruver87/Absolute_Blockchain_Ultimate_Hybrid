#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rate Limiter - защита от DDoS и спама"""

import time
import threading
from collections import defaultdict
from typing import Dict, Tuple, Optional

class RateLimiter:
    """Токен-бакинг rate limiter"""
    
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.tokens: Dict[str, float] = defaultdict(float)
        self.last_refill: Dict[str, float] = defaultdict(float)
        self.lock = threading.RLock()
    
    def _refill_tokens(self, key: str) -> None:
        """Пополнение токенов"""
        now = time.time()
        last = self.last_refill[key]
        time_passed = now - last
        refill = time_passed / 60.0 * self.requests_per_minute
        
        current = self.tokens[key]
        self.tokens[key] = min(self.requests_per_minute, current + refill)
        self.last_refill[key] = now
    
    def allow_request(self, key: str) -> Tuple[bool, int]:
        """
        Проверяет, можно ли выполнить запрос
        Возвращает: (разрешено, осталось_токенов)
        """
        with self.lock:
            self._refill_tokens(key)
            
            if self.tokens[key] >= 1:
                self.tokens[key] -= 1
                return True, int(self.tokens[key])
            else:
                return False, 0
    
    def get_remaining(self, key: str) -> int:
        """Получить оставшиеся токены"""
        with self.lock:
            self._refill_tokens(key)
            return int(self.tokens[key])
    
    def reset(self, key: str) -> None:
        """Сбросить лимит для ключа"""
        with self.lock:
            self.tokens[key] = self.requests_per_minute
            self.last_refill[key] = time.time()

# Глобальный экземпляр
rate_limiter = RateLimiter()
