# execution/mempool.py
"""
Transaction Mempool with gas priority and nonce ordering
"""

import time
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import threading


@dataclass
class Transaction:
    """Transaction structure"""
    hash: str
    from_addr: str
    to_addr: str
    value: int
    gas_limit: int
    gas_price: int
    nonce: int
    data: bytes = b""
    signature: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def get_total_gas_cost(self) -> int:
        return self.gas_limit * self.gas_price


class Mempool:
    """
    Transaction pool with:
    - Gas price sorting
    - Nonce ordering per address
    - Double-spend protection
    """
    
    def __init__(self, max_size: int = 10000):
        self.pending: Dict[str, Transaction] = {}  # tx_hash -> tx
        self.nonce_tracker: Dict[str, int] = {}   # address -> last_nonce
        self.max_size = max_size
        self.lock = threading.RLock()
    
    def add_transaction(self, tx: Transaction) -> bool:
        """Add transaction to mempool"""
        with self.lock:
            # Check if full
            if len(self.pending) >= self.max_size:
                self._cleanup_low_gas()
                if len(self.pending) >= self.max_size:
                    return False
            
            # Check for duplicate
            if tx.hash in self.pending:
                return False
            
            # Check nonce ordering
            expected_nonce = self.nonce_tracker.get(tx.from_addr, 0)
            if tx.nonce < expected_nonce:
                return False  # Already processed
            
            self.pending[tx.hash] = tx
            return True
    
    def get_sorted_transactions(self, limit: int = 100) -> List[Transaction]:
        """
        Get transactions sorted by:
        1. Gas price (highest first)
        2. Nonce (lowest first per address)
        """
        with self.lock:
            txs = list(self.pending.values())
            
            # Group by address for nonce ordering
            by_address: Dict[str, List[Transaction]] = {}
            for tx in txs:
                if tx.from_addr not in by_address:
                    by_address[tx.from_addr] = []
                by_address[tx.from_addr].append(tx)
            
            # Sort each address's txs by nonce
            for addr in by_address:
                by_address[addr].sort(key=lambda tx: tx.nonce)
            
            # Flatten and sort by gas price
            all_txs = []
            for addr_txs in by_address.values():
                all_txs.extend(addr_txs)
            
            all_txs.sort(key=lambda tx: -tx.gas_price)
            
            return all_txs[:limit]
    
    def remove_transaction(self, tx_hash: str) -> bool:
        """Remove transaction from mempool (after inclusion)"""
        with self.lock:
            if tx_hash in self.pending:
                tx = self.pending[tx_hash]
                # Update nonce tracker
                current = self.nonce_tracker.get(tx.from_addr, 0)
                if tx.nonce >= current:
                    self.nonce_tracker[tx.from_addr] = tx.nonce + 1
                del self.pending[tx_hash]
                return True
            return False
    
    def get_pending_count(self) -> int:
        with self.lock:
            return len(self.pending)
    
    def get_transaction(self, tx_hash: str) -> Optional[Transaction]:
        with self.lock:
            return self.pending.get(tx_hash)
    
    def _cleanup_low_gas(self):
        """Remove lowest gas transactions when full"""
        if len(self.pending) < self.max_size * 0.9:
            return
        
        sorted_txs = sorted(
            self.pending.values(),
            key=lambda tx: tx.gas_price
        )
        to_remove = len(self.pending) - int(self.max_size * 0.8)
        for tx in sorted_txs[:to_remove]:
            del self.pending[tx.hash]
    
    def get_stats(self) -> dict:
        with self.lock:
            if not self.pending:
                return {"size": 0, "avg_gas_price": 0, "total_value": 0}
            
            gas_prices = [tx.gas_price for tx in self.pending.values()]
            total_value = sum(tx.value for tx in self.pending.values())
            
            return {
                "size": len(self.pending),
                "avg_gas_price": sum(gas_prices) // len(gas_prices),
                "min_gas_price": min(gas_prices),
                "max_gas_price": max(gas_prices),
                "total_value": total_value
            }
    
    def clear(self):
        with self.lock:
            self.pending.clear()
            self.nonce_tracker.clear()


def create_transaction(from_addr: str, to_addr: str, value: int,
                       gas_limit: int = 21000, gas_price: int = 1,
                       nonce: int = 0) -> Transaction:
    """Helper to create a transaction"""
    tx_data = f"{from_addr}{to_addr}{value}{nonce}{time.time()}"
    tx_hash = hashlib.sha256(tx_data.encode()).hexdigest()[:32]
    
    return Transaction(
        hash=tx_hash,
        from_addr=from_addr,
        to_addr=to_addr,
        value=value,
        gas_limit=gas_limit,
        gas_price=gas_price,
        nonce=nonce
    )
