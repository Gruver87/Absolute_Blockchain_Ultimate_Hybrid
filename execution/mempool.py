# execution/mempool.py - Working mempool
import time
import hashlib
import json
from typing import Dict, List, Optional
from collections import OrderedDict

class Mempool:
    def __init__(self, max_size: int = 1000):
        self.transactions: Dict[str, dict] = {}
        self.max_size = max_size
        self.pending_count = 0
        
    def add_transaction(self, tx: dict) -> str:
        """Add transaction to mempool and return hash"""
        tx_hash = self._calculate_hash(tx)
        
        if tx_hash in self.transactions:
            return tx_hash
            
        if len(self.transactions) >= self.max_size:
            # Remove oldest transaction
            oldest = list(self.transactions.keys())[0]
            del self.transactions[oldest]
        
        tx['hash'] = tx_hash
        tx['timestamp'] = time.time()
        self.transactions[tx_hash] = tx
        self.pending_count = len(self.transactions)
        
        print(f"   📝 Transaction added to mempool: {tx_hash[:16]}...")
        return tx_hash
    
    def get_sorted_transactions(self, limit: int = None) -> List[dict]:
        """Get transactions sorted by gas price (highest first)"""
        if limit is None:
            limit = len(self.transactions)
        
        sorted_txs = sorted(
            self.transactions.values(),
            key=lambda x: int(x.get('gasPrice', '0x1'), 16),
            reverse=True
        )
        return sorted_txs[:limit]
    
    def remove_transactions(self, tx_hashes: List[str]):
        """Remove transactions after block inclusion"""
        for tx_hash in tx_hashes:
            if tx_hash in self.transactions:
                del self.transactions[tx_hash]
        self.pending_count = len(self.transactions)
    
    def get_pending_count(self) -> int:
        return len(self.transactions)
    
    def get_transaction(self, tx_hash: str) -> Optional[dict]:
        return self.transactions.get(tx_hash)
    
    def _calculate_hash(self, tx: dict) -> str:
        """Calculate transaction hash"""
        tx_copy = {k: v for k, v in tx.items() if k not in ['hash', 'timestamp']}
        tx_string = json.dumps(tx_copy, sort_keys=True)
        return hashlib.sha256(tx_string.encode()).hexdigest()[:16]
    
    def clear(self):
        self.transactions.clear()
        self.pending_count = 0
