"""
Rate Limiter - защита от спама
"""

import time
from collections import defaultdict
from typing import Tuple, Optional

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: dict = defaultdict(list)
    
    def check(self, client_ip: str) -> Tuple[bool, Optional[int]]:
        now = time.time()
        window = 60
        
        self.requests[client_ip] = [
            t for t in self.requests[client_ip] 
            if now - t < window
        ]
        
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return False, 60
        
        self.requests[client_ip].append(now)
        return True, None
    
    def get_stats(self, client_ip: str) -> dict:
        now = time.time()
        recent = [t for t in self.requests.get(client_ip, []) if now - t < 60]
        return {
            'ip': client_ip,
            'requests_last_minute': len(recent),
            'limit': self.requests_per_minute
        }

rate_limiter = RateLimiter()

def check_rate_limit(handler) -> Tuple[bool, Optional[str]]:
    allowed, wait = rate_limiter.check(handler.client_address[0])
    if not allowed:
        return False, f"Rate limit exceeded. Try again in {wait} seconds."
    return True, None
