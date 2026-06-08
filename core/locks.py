# core/locks.py
# ABSOLUTE BLOCKCHAIN - THREADING LOCKS
# ЗАЩИТА ОТ RACE CONDITIONS И ПАРАЛЛЕЛЬНЫХ МАЙНИНГОВ

import threading
import time
from typing import Dict, Any, Optional
from functools import wraps

# ============================================================================
# БЛОКИРОВКИ ДЛЯ РАЗНЫХ КОМПОНЕНТОВ
# ============================================================================

class ThreadSafeMempool:
    """Потокобезопасный пул транзакций"""
    
    def __init__(self, max_size: int = 10000):
        self.transactions = []
        self.max_size = max_size
        self._lock = threading.RLock()
        self._total_processed = 0
        self._total_rejected = 0
    
    def add(self, tx) -> bool:
        """Потокобезопасное добавление транзакции"""
        with self._lock:
            # Проверка на дубликат
            tx_hash = tx.tx_hash if hasattr(tx, 'tx_hash') else tx.hash if hasattr(tx, 'hash') else str(tx)
            for existing in self.transactions:
                existing_hash = existing.tx_hash if hasattr(existing, 'tx_hash') else existing.hash if hasattr(existing, 'hash') else str(existing)
                if existing_hash == tx_hash:
                    self._total_rejected += 1
                    return False
            
            # Ограничение размера
            if len(self.transactions) >= self.max_size:
                self.transactions.pop(0)
            
            self.transactions.append(tx)
            self._total_processed += 1
            return True
    
    def remove(self, tx_hash: str) -> bool:
        """Потокобезопасное удаление транзакции"""
        with self._lock:
            for i, tx in enumerate(self.transactions):
                current_hash = tx.tx_hash if hasattr(tx, 'tx_hash') else tx.hash if hasattr(tx, 'hash') else str(tx)
                if current_hash == tx_hash:
                    self.transactions.pop(i)
                    return True
            return False
    
    def get_all(self, limit: int = 100) -> list:
        """Потокобезопасное получение транзакций"""
        with self._lock:
            return self.transactions[:limit]
    
    def size(self) -> int:
        with self._lock:
            return len(self.transactions)
    
    def clear(self):
        with self._lock:
            self.transactions.clear()
    
    def get_stats(self) -> Dict:
        with self._lock:
            return {
                'size': len(self.transactions),
                'max_size': self.max_size,
                'processed': self._total_processed,
                'rejected': self._total_rejected,
                'utilization': round(len(self.transactions) / self.max_size * 100, 2)
            }

class BlockchainLocks:
    """Централизованное управление блокировками блокчейна"""
    
    def __init__(self):
        # Основные блокировки
        self.chain_lock = threading.RLock()  # Для модификации цепочки
        self.mining_lock = threading.Lock()   # Только один майнинг за раз
        self.mempool_lock = threading.RLock() # Для мемпула
        self.state_lock = threading.RLock()   # Для состояния (балансы)
        self.storage_lock = threading.RLock() # Для хранилища
        self.p2p_lock = threading.RLock()     # Для P2P сети
        
        # Счётчики для мониторинга
        self._lock_stats = {
            'chain': 0, 'mining': 0, 'mempool': 0,
            'state': 0, 'storage': 0, 'p2p': 0
        }
    
    def acquire(self, lock_name: str, blocking: bool = True) -> bool:
        """Безопасный захват блокировки"""
        lock = getattr(self, f"{lock_name}_lock", None)
        if not lock:
            return False
        
        acquired = lock.acquire(blocking=blocking)
        if acquired:
            self._lock_stats[lock_name] += 1
        return acquired
    
    def release(self, lock_name: str):
        """Освобождение блокировки"""
        lock = getattr(self, f"{lock_name}_lock", None)
        if lock and lock.locked():
            lock.release()
    
    @property
    def stats(self) -> Dict:
        return self._lock_stats.copy()

# ============================================================================
# ДЕКОРАТОРЫ ДЛЯ ПОТОКОБЕЗОПАСНЫХ МЕТОДОВ
# ============================================================================

def thread_safe(lock_name: str):
    """Декоратор для автоматической блокировки методов"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            locks = getattr(self, 'locks', None)
            if locks and hasattr(locks, 'acquire'):
                locks.acquire(lock_name)
                try:
                    return func(self, *args, **kwargs)
                finally:
                    locks.release(lock_name)
            else:
                return func(self, *args, **kwargs)
        return wrapper
    return decorator

# ============================================================================
# RATE LIMITER ДЛЯ API
# ============================================================================

class RateLimiter:
    """Защита API от DDoS"""
    
    def __init__(self, requests_per_minute: int = 120):
        self.requests_per_minute = requests_per_minute
        self._requests = {}
        self._lock = threading.RLock()
    
    def check(self, client_ip: str) -> tuple:
        """Проверка лимита, возвращает (разрешено, сообщение)"""
        now = time.time()
        window = 60  # 1 минута
        
        with self._lock:
            # Очищаем старые записи
            if client_ip in self._requests:
                self._requests[client_ip] = [
                    t for t in self._requests[client_ip]
                    if now - t < window
                ]
            else:
                self._requests[client_ip] = []
            
            # Проверка лимита
            if len(self._requests[client_ip]) >= self.requests_per_minute:
                return False, f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
            
            self._requests[client_ip].append(now)
            return True, "OK"
    
    def reset(self, client_ip: str):
        """Сброс лимита для IP"""
        with self._lock:
            if client_ip in self._requests:
                del self._requests[client_ip]

# Глобальные экземпляры
mempool = ThreadSafeMempool()
rate_limiter = RateLimiter()
locks = BlockchainLocks()

if __name__ == "__main__":
    print("=" * 60)
    print("Threading Locks - Тест")
    print("=" * 60)
    
    # Тест мемпула
    for i in range(10):
        mempool.add(f"tx{i}")
    print(f"✅ Mempool size: {mempool.size()}")
    print(f"📊 Mempool stats: {mempool.get_stats()}")
    
    # Тест rate limiter
    allowed, msg = rate_limiter.check("127.0.0.1")
    print(f"✅ Rate limiter: {msg}")
    
    print("\n✅ Locks и Rate Limiter готовы!")
