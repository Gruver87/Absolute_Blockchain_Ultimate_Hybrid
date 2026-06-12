# Новый27ч1.py - Fixed
from datetime import datetime

class Order:
    def __init__(self, timestamp: float = None, valid_until: float = None):
        self.timestamp = timestamp or datetime.now().timestamp()
        self.valid_until = valid_until or self.timestamp + 86400
    
    def is_valid(self) -> bool:
        return datetime.now().timestamp() < self.valid_until

def init():
    return {"success": True, "module": "Новый27ч1"}
