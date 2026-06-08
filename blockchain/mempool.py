"""
Mempool - пул неподтверждённых транзакций
"""

import threading
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field

@dataclass
class MempoolTransaction:
    tx_hash: str
    from_addr: str
    to_addr: str
    amount: float
    fee: float
    timestamp: float
    signature: str = ''
    added_at: float = field(default_factory=time.time)

class Mempool:
    def __init__(self, max_size: int = 10000, min_fee: float = 0.0001):
        self.transactions: Dict[str, MempoolTransaction] = {}
        self.max_size = max_size
        self.min_fee = min_fee
        self.lock = threading.RLock()
    
    def add_transaction(self, tx: MempoolTransaction) -> bool:
        with self.lock:
            if tx.tx_hash in self.transactions:
                return False
            if tx.fee < self.min_fee:
                return False
            if len(self.transactions) >= self.max_size:
                return False
            self.transactions[tx.tx_hash] = tx
            return True
    
    def get_transactions(self, limit: int = 100) -> List[MempoolTransaction]:
        with self.lock:
            sorted_txs = sorted(
                self.transactions.values(),
                key=lambda x: x.fee,
                reverse=True
            )
            return sorted_txs[:limit]
    
    def remove_transaction(self, tx_hash: str) -> bool:
        with self.lock:
            if tx_hash in self.transactions:
                del self.transactions[tx_hash]
                return True
            return False
    
    def get_size(self) -> int:
        with self.lock:
            return len(self.transactions)
    
    def get_stats(self) -> dict:
        with self.lock:
            if not self.transactions:
                return {'size': 0, 'total_fees': 0, 'avg_fee': 0}
            fees = [tx.fee for tx in self.transactions.values()]
            return {
                'size': len(self.transactions),
                'total_fees': sum(fees),
                'avg_fee': sum(fees) / len(fees)
            }
