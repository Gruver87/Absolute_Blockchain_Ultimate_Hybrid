# core/mempool.py
# НАСТОЯЩИЙ MEMPOOL С СОРТИРОВКОЙ ПО FEE

import threading
import time
from typing import List, Dict, Optional

class Mempool:
    def __init__(self, max_size: int = 10000):
        self.transactions = []
        self.max_size = max_size
        self.lock = threading.RLock()
        self.pending_nonces = {}
    
    def add_transaction(self, tx) -> bool:
        with self.lock:
            # Проверка подписи
            if not tx.verify():
                return False
            
            # Проверка дубликата
            for existing in self.transactions:
                if existing.tx_hash == tx.tx_hash:
                    return False
            
            # Проверка nonce
            expected_nonce = self.pending_nonces.get(tx.from_addr, 0)
            if tx.nonce < expected_nonce:
                return False
            
            # Ограничение размера
            if len(self.transactions) >= self.max_size:
                # Удаляем самые старые с низким fee
                self.transactions.sort(key=lambda t: t.fee, reverse=True)
                self.transactions = self.transactions[:self.max_size]
            
            self.transactions.append(tx)
            return True
    
    def remove_transaction(self, tx_hash: str):
        with self.lock:
            for i, tx in enumerate(self.transactions):
                if tx.tx_hash == tx_hash:
                    self.pending_nonces[tx.from_addr] = max(
                        self.pending_nonces.get(tx.from_addr, 0),
                        tx.nonce + 1
                    )
                    self.transactions.pop(i)
                    return True
            return False
    
    def get_transactions(self, limit: int = 100) -> List:
        with self.lock:
            # Сортировка по fee (высокие приоритетнее)
            sorted_txs = sorted(self.transactions, key=lambda t: t.fee, reverse=True)
            result = sorted_txs[:limit]
            return result
    
    def size(self) -> int:
        return len(self.transactions)
    
    def clear(self):
        with self.lock:
            self.transactions.clear()

# Тест
if __name__ == "__main__":
    print("=" * 60)
    print("Mempool - Тест")
    print("=" * 60)
    
    from crypto.wallet import Wallet
    from core.transaction import Transaction
    
    mempool = Mempool()
    wallet = Wallet.create_wallet()
    
    for i in range(10):
        tx = Transaction.create_transfer(wallet['address'], "receiver", 100, wallet['private_key'], i)
        mempool.add_transaction(tx)
    
    print(f"\n✅ Mempool size: {mempool.size()}")
    txs = mempool.get_transactions(5)
    print(f"✅ Получено транзакций: {len(txs)}")
    
    print("\n✅ Mempool готов!")
