# dynamic_sharding.py - COMPLETE SHARDING IMPLEMENTATION
import hashlib
import threading
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import random

@dataclass
class Shard:
    """Individual shard in the blockchain"""
    id: int
    name: str
    nodes: List[str] = field(default_factory=list)
    transactions: List[dict] = field(default_factory=list)
    block_height: int = 0
    last_hash: str = "0" * 64
    state_root: str = "0" * 64

@dataclass
class CrossShardTransaction:
    """Transaction between different shards"""
    tx_id: str
    from_shard: int
    to_shard: int
    from_addr: str
    to_addr: str
    amount: int
    status: str  # pending, confirmed, failed
    created_at: float
    confirmed_at: Optional[float] = None

class ShardingManager:
    """Complete sharding system for blockchain scalability"""

    def __init__(self, num_shards: int = 4, db=None):
        self.num_shards = num_shards
        self.shards: Dict[int, Shard] = {}
        self.cross_shard_txs: Dict[str, CrossShardTransaction] = {}
        self.pending_cross_txs: List[str] = []
        self.node_to_shard: Dict[str, int] = {}
        self.shard_lock = threading.Lock()
        self._db = db
        self._initialize_shards()

    def set_database(self, db) -> None:
        """Attach chain database for real balance lookups."""
        self._db = db

    def _initialize_shards(self):
        """Initialize shards"""
        shard_names = ["Genesis", "Finance", "Governance", "Identity", "Data"]
        for i in range(self.num_shards):
            self.shards[i] = Shard(
                id=i,
                name=shard_names[i % len(shard_names)],
                nodes=[]
            )

    def get_shard_for_address(self, address: str) -> int:
        """Determine which shard an address belongs to"""
        hash_val = int(hashlib.sha256(address.encode()).hexdigest(), 16)
        return hash_val % self.num_shards

    def get_shard_for_transaction(self, tx: dict) -> int:
        """Determine shard for transaction"""
        from_addr = tx.get('from', '')
        return self.get_shard_for_address(from_addr)

    def add_transaction(self, tx: dict) -> tuple:
        """Add transaction to appropriate shard"""
        from_shard = self.get_shard_for_address(tx.get('from', ''))
        to_shard = self.get_shard_for_address(tx.get('to', ''))

        if from_shard == to_shard:
            with self.shard_lock:
                self.shards[from_shard].transactions.append(tx)
            return from_shard, None
        else:
            tx_id = hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest()[:16]
            cross_tx = CrossShardTransaction(
                tx_id=tx_id,
                from_shard=from_shard,
                to_shard=to_shard,
                from_addr=tx.get('from', ''),
                to_addr=tx.get('to', ''),
                amount=int(tx.get('value', '0x0'), 16) if isinstance(tx.get('value'), str) else tx.get('value', 0),
                status="pending",
                created_at=time.time()
            )
            self.cross_shard_txs[tx_id] = cross_tx
            self.pending_cross_txs.append(tx_id)
            return from_shard, tx_id

    def process_cross_shard_transactions(self):
        """Process pending cross-shard transactions"""
        for tx_id in self.pending_cross_txs[:]:
            tx = self.cross_shard_txs[tx_id]
            if self._validate_cross_shard_tx(tx):
                tx.status = "confirmed"
                tx.confirmed_at = time.time()
                self.pending_cross_txs.remove(tx_id)

    def _validate_cross_shard_tx(self, tx: CrossShardTransaction) -> bool:
        """Validate cross-shard transaction against chain balances."""
        if tx.amount <= 0:
            return False
        if not tx.from_addr or not tx.to_addr:
            return False
        if self._db and hasattr(self._db, "get_balance"):
            balance = float(self._db.get_balance(tx.from_addr))
            return balance >= float(tx.amount)
        return True

    def get_shard_balance(self, address: str, shard_id: int = None) -> float:
        """Balance for address (logical shard routing; funds live on L1 state)."""
        if shard_id is None:
            shard_id = self.get_shard_for_address(address)
        if self._db and hasattr(self._db, "get_balance"):
            return float(self._db.get_balance(address))
        return 0.0

    def get_shard_state(self, shard_id: int) -> dict:
        """Get state of a specific shard"""
        if shard_id not in self.shards:
            return {}
        shard = self.shards[shard_id]
        return {
            "id": shard.id,
            "name": shard.name,
            "nodes": len(shard.nodes),
            "transactions": len(shard.transactions),
            "block_height": shard.block_height,
            "last_hash": shard.last_hash
        }

    def get_all_shards_state(self) -> dict:
        """Get state of all shards"""
        return {
            "num_shards": self.num_shards,
            "shards": [self.get_shard_state(i) for i in range(self.num_shards)],
            "pending_cross_txs": len(self.pending_cross_txs),
            "total_cross_txs": len(self.cross_shard_txs)
        }

    def register_node(self, node_id: str, shard_id: int = None):
        """Register a node to a shard"""
        if shard_id is None:
            shard_id = hash(node_id) % self.num_shards
        self.node_to_shard[node_id] = shard_id
        self.shards[shard_id].nodes.append(node_id)

    def mine_shard_block(self, shard_id: int) -> Optional[dict]:
        """Mine a block for a specific shard"""
        shard = self.shards.get(shard_id)
        if not shard or not shard.transactions:
            return None

        transactions = shard.transactions[:100]
        shard.transactions = shard.transactions[100:]

        block = {
            "height": shard.block_height,
            "shard_id": shard_id,
            "transactions": transactions,
            "prev_hash": shard.last_hash,
            "timestamp": time.time(),
            "state_root": hashlib.sha256(json.dumps(transactions).encode()).hexdigest()[:16]
        }

        block_string = f"{block['height']}{block['shard_id']}{block['transactions']}{block['prev_hash']}{block['timestamp']}"
        block['hash'] = hashlib.sha256(block_string.encode()).hexdigest()[:16]

        shard.block_height += 1
        shard.last_hash = block['hash']

        return block

    def get_stats(self) -> dict:
        """Get sharding statistics"""
        return {
            "enabled": True,
            "tier": "routing",
            "balance_source": "chain_state" if self._db else "unavailable",
            "total_shards": self.num_shards,
            "total_transactions": sum(len(s.transactions) for s in self.shards.values()),
            "total_cross_shard_txs": len(self.cross_shard_txs),
            "pending_cross_shard_txs": len(self.pending_cross_txs),
            "shard_details": [
                {
                    "id": s.id,
                    "name": s.name,
                    "nodes": len(s.nodes),
                    "txs": len(s.transactions),
                    "height": s.block_height
                }
                for s in self.shards.values()
            ]
        }


# Global instance for import
sharding_manager = ShardingManager()

if __name__ == "__main__":
    sharding = ShardingManager(num_shards=4)
    print("\nSharding Stats:")
    print(json.dumps(sharding.get_stats(), indent=2))
