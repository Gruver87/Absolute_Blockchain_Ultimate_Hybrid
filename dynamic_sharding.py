# dynamic_sharding.py - Система шардинга
import hashlib
import time
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

@dataclass
class Shard:
    """Шард блокчейна"""
    shard_id: int
    name: str
    transactions: List[Dict] = field(default_factory=list)
    block_height: int = 0
    last_hash: str = "0" * 64

class ShardingManager:
    """Управление шардами"""
    
    SHARD_NAMES = {
        0: "Genesis Shard",
        1: "Finance Shard", 
        2: "Governance Shard",
        3: "Identity Shard"
    }
    
    def __init__(self, num_shards: int = 4):
        self.num_shards = num_shards
        self.shards: Dict[int, Shard] = {}
        self.shard_map: Dict[str, int] = {}
        self.lock = threading.RLock()
        self._init_shards()
    
    def _init_shards(self):
        for i in range(self.num_shards):
            self.shards[i] = Shard(i, self.SHARD_NAMES.get(i, f"Shard {i}"))
    
    def get_shard_for_address(self, address: str) -> int:
        """Определить шард для адреса"""
        hash_val = int(hashlib.sha256(address.encode()).hexdigest(), 16)
        return hash_val % self.num_shards
    
    def add_transaction(self, tx: Dict) -> int:
        """Добавить транзакцию в соответствующий шард"""
        shard_id = self.get_shard_for_address(tx.get('from', ''))
        with self.lock:
            self.shards[shard_id].transactions.append(tx)
        return shard_id
    
    def get_shard_transactions(self, shard_id: int, limit: int = 100) -> List[Dict]:
        """Получить транзакции шарда"""
        with self.lock:
            return self.shards[shard_id].transactions[-limit:]
    
    def get_shard_stats(self, shard_id: int) -> Dict:
        with self.lock:
            shard = self.shards.get(shard_id)
            if not shard:
                return {}
            return {
                'shard_id': shard.shard_id,
                'name': shard.name,
                'transaction_count': len(shard.transactions),
                'block_height': shard.block_height
            }
    
    def get_all_stats(self) -> List[Dict]:
        return [self.get_shard_stats(i) for i in range(self.num_shards)]
    
    def process_shard_block(self, shard_id: int, miner: str) -> Optional[Dict]:
        """Обработать блок шарда (мини-блок)"""
        with self.lock:
            shard = self.shards[shard_id]
            if not shard.transactions:
                return None
            
            block = {
                'shard_id': shard_id,
                'height': shard.block_height + 1,
                'transactions': shard.transactions[:10],
                'miner': miner,
                'timestamp': time.time(),
                'prev_hash': shard.last_hash
            }
            
            # Вычисляем хэш блока
            block_data = f"{block['height']}{block['prev_hash']}{block['timestamp']}{json.dumps(block['transactions'])}"
            block['block_hash'] = hashlib.sha256(block_data.encode()).hexdigest()[:16]
            
            shard.block_height = block['height']
            shard.last_hash = block['block_hash']
            shard.transactions = shard.transactions[10:]  # Убираем обработанные
            
            return block

# Глобальный экземпляр
sharding_manager = ShardingManager()
