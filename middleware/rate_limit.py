#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rate Limiter - защита от DDoS и спама"""

import time
from collections import defaultdict
from typing import Tuple

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

# Глобальный экземпляр
rate_limiter = RateLimiter()
