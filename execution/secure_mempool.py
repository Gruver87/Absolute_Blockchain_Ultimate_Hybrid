# execution/secure_mempool.py
"""
Secure mempool with signature and nonce validation
"""

import time
import threading
import hashlib
import json
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class SignedTransaction:
    """Signed transaction with metadata"""
    hash: str
    from_addr: str
    to_addr: str
    value: int
    nonce: int
    signature: str
    public_key: str
    chain_id: int
    timestamp: float
    gas_price: int = 1
    gas_limit: int = 21000


class SecureMempool:
    """Mempool with signature validation and nonce ordering"""
    
    def __init__(self, state_engine, max_size: int = 10000):
        self.state_engine = state_engine
        self.pending: Dict[str, SignedTransaction] = {}
        self.max_size = max_size
        self.lock = threading.RLock()
    
    def _verify_signature(self, tx: dict) -> bool:
        """Verify transaction signature"""
        try:
            from crypto.wallet import verify_transaction_signature
            return verify_transaction_signature(tx)
        except:
            return False
    
    def add_transaction(self, tx_data: dict) -> tuple[bool, str]:
        """
        Add transaction after full validation:
        1. Signature verification
        2. Nonce check
        3. Balance check
        """
        with self.lock:
            # Check signature
            if not self._verify_signature(tx_data):
                return False, "Invalid signature"
            
            # Check nonce
            expected_nonce = self.state_engine.get_nonce(tx_data["from"])
            if tx_data["nonce"] != expected_nonce:
                return False, f"Invalid nonce: expected {expected_nonce}, got {tx_data['nonce']}"
            
            # Check balance
            balance = self.state_engine.get_balance(tx_data["from"])
            total_cost = tx_data["value"] + (tx_data.get("gas_price", 1) * tx_data.get("gas_limit", 21000))
            if balance < total_cost:
                return False, f"Insufficient balance: {balance} < {total_cost}"
            
            # Check chain_id
            if tx_data.get("chain_id", 1) != 1:
                return False, f"Invalid chain_id: {tx_data.get('chain_id')}"
            
            # Create transaction object
            tx = SignedTransaction(
                hash=tx_data["hash"],
                from_addr=tx_data["from"],
                to_addr=tx_data["to"],
                value=tx_data["value"],
                nonce=tx_data["nonce"],
                signature=tx_data["signature"],
                public_key=tx_data["public_key"],
                chain_id=tx_data.get("chain_id", 1),
                timestamp=time.time(),
                gas_price=tx_data.get("gas_price", 1),
                gas_limit=tx_data.get("gas_limit", 21000)
            )
            
            # Check for duplicate
            if tx.hash in self.pending:
                return False, "Transaction already in mempool"
            
            # Check size limit
            if len(self.pending) >= self.max_size:
                return False, "Mempool full"
            
            self.pending[tx.hash] = tx
            return True, "Transaction added"
    
    def get_sorted_transactions(self, limit: int = 100) -> List[SignedTransaction]:
        """Get transactions sorted by gas price (highest first) and nonce"""
        with self.lock:
            sorted_txs = sorted(
                self.pending.values(),
                key=lambda tx: (-tx.gas_price, tx.nonce)
            )
            return sorted_txs[:limit]
    
    def remove_transaction(self, tx_hash: str) -> bool:
        with self.lock:
            if tx_hash in self.pending:
                del self.pending[tx_hash]
                return True
            return False
    
    def get_pending_count(self) -> int:
        with self.lock:
            return len(self.pending)
    
    def get_transaction(self, tx_hash: str) -> Optional[SignedTransaction]:
        with self.lock:
            return self.pending.get(tx_hash)
    
    def clear(self):
        with self.lock:
            self.pending.clear()
    
    def get_stats(self) -> dict:
        with self.lock:
            if not self.pending:
                return {"size": 0, "avg_gas_price": 0}
            
            gas_prices = [tx.gas_price for tx in self.pending.values()]
            return {
                "size": len(self.pending),
                "avg_gas_price": sum(gas_prices) // len(gas_prices),
                "min_gas_price": min(gas_prices),
                "max_gas_price": max(gas_prices)
            }
