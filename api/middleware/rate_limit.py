# api/middleware/rate_limit.py
import time
from collections import defaultdict

class RateLimiter:
    """Простой rate limiter для защиты от спама"""
    
    def __init__(self, requests_per_minute=60):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
    
    def check(self, client_ip: str) -> bool:
        now = time.time()
        window = 60  # 1 минута
        
        # Очищаем старые запросы
        self.requests[client_ip] = [
            t for t in self.requests[client_ip]
            if now - t < window
        ]
        
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return False
        
        self.requests[client_ip].append(now)
        return True

# Глобальный экземпляр
rate_limiter = RateLimiter(requests_per_minute=60)
