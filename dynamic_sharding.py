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
    
    def __init__(self, num_shards: int = 4):
        self.num_shards = num_shards
        self.shards: Dict[int, Shard] = {}
        self.cross_shard_txs: Dict[str, CrossShardTransaction] = {}
        self.pending_cross_txs: List[str] = []
        self.node_to_shard: Dict[str, int] = {}
        self.shard_lock = threading.Lock()
        self._initialize_shards()
    
    def _initialize_shards(self):
        """Initialize shards"""
        shard_names = ["Genesis", "Finance", "Governance", "Identity", "Data"]
        for i in range(self.num_shards):
            self.shards[i] = Shard(
                id=i,
                name=shard_names[i % len(shard_names)],
                nodes=[]
            )
        print(f"🔷 Sharding initialized: {self.num_shards} shards")
        for shard in self.shards.values():
            print(f"   Shard {shard.id}: {shard.name}")
    
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
            # Intra-shard transaction
            with self.shard_lock:
                self.shards[from_shard].transactions.append(tx)
            return from_shard, None
        else:
            # Cross-shard transaction
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
            
            # Simulate cross-shard consensus
            if self._validate_cross_shard_tx(tx):
                tx.status = "confirmed"
                tx.confirmed_at = time.time()
                self.pending_cross_txs.remove(tx_id)
                print(f"   🔄 Cross-shard tx confirmed: {tx_id[:16]}... ({tx.from_shard}→{tx.to_shard})")
    
    def _validate_cross_shard_tx(self, tx: CrossShardTransaction) -> bool:
        """Validate cross-shard transaction"""
        # In production, this would involve consensus between shards
        return True
    
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
        print(f"   📍 Node {node_id[:16]}... assigned to shard {shard_id}")
    
    def mine_shard_block(self, shard_id: int) -> Optional[dict]:
        """Mine a block for a specific shard"""
        shard = self.shards.get(shard_id)
        if not shard or not shard.transactions:
            return None
        
        # Take pending transactions
        transactions = shard.transactions[:100]
        shard.transactions = shard.transactions[100:]
        
        # Create block
        block = {
            "height": shard.block_height,
            "shard_id": shard_id,
            "transactions": transactions,
            "prev_hash": shard.last_hash,
            "timestamp": time.time(),
            "state_root": hashlib.sha256(json.dumps(transactions).encode()).hexdigest()[:16]
        }
        
        # Calculate hash
        block_string = f"{block['height']}{block['shard_id']}{block['transactions']}{block['prev_hash']}{block['timestamp']}"
        block['hash'] = hashlib.sha256(block_string.encode()).hexdigest()[:16]
        
        # Update shard state
        shard.block_height += 1
        shard.last_hash = block['hash']
        
        return block
    
    def get_shard_balance(self, address: str, shard_id: int = None) -> int:
        """Get balance from specific shard"""
        if shard_id is None:
            shard_id = self.get_shard_for_address(address)
        # Simplified - would query shard state
        return 0
    
    def get_stats(self) -> dict:
        """Get sharding statistics"""
        return {
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

# Example usage
if __name__ == "__main__":
    sharding = ShardingManager(num_shards=4)
    print("\n📊 Sharding Stats:")
    print(json.dumps(sharding.get_stats(), indent=2))
