#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN - DYNAMIC SHARDING
Автоматическое масштабирование сети
"""

import time
import threading
import hashlib
import json
from typing import Dict, List, Any, Optional
from collections import defaultdict

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

class ShardingConfig:
    INITIAL_SHARDS = 4
    MAX_SHARDS = 64
    MIN_SHARDS = 2
    TPS_THRESHOLD_HIGH = 100  # Создаём новый шард при TPS > 100
    TPS_THRESHOLD_LOW = 20    # Объединяем шарды при TPS < 20
    REBALANCE_INTERVAL = 60   # Проверка каждые 60 секунд

# ============================================================================
# ШАРД
# ============================================================================

class Shard:
    def __init__(self, shard_id: int):
        self.shard_id = shard_id
        self.name = f"Shard_{shard_id:03d}"
        self.transactions = []
        self.blocks = []
        self.pending_txs = []
        self.state_root = hashlib.sha256(b'empty').hexdigest()
        self.created_at = int(time.time())
        self.last_updated = self.created_at
        self.tx_count = 0
        self.total_volume = 0.0
        self.tps = 0.0
        self.tps_history = []
        self.lock = threading.RLock()
    
    def add_transaction(self, tx: Dict) -> bool:
        with self.lock:
            tx['shard_id'] = self.shard_id
            tx['shard_timestamp'] = int(time.time())
            self.pending_txs.append(tx)
            self.tx_count += 1
            self.total_volume += tx.get('amount', 0)
            self.last_updated = int(time.time())
            self._update_tps()
            return True
    
    def _update_tps(self):
        now = time.time()
        self.tps_history.append((now, len(self.pending_txs)))
        self.tps_history = [(ts, count) for ts, count in self.tps_history if now - ts < 60]
        
        if len(self.tps_history) > 1:
            total_txs = sum(count for _, count in self.tps_history)
            self.tps = total_txs / 60
    
    def get_load(self) -> float:
        with self.lock:
            return self.tps
    
    def get_stats(self) -> Dict:
        with self.lock:
            return {
                'shard_id': self.shard_id,
                'name': self.name,
                'tx_count': self.tx_count,
                'total_volume': self.total_volume,
                'tps': round(self.tps, 2),
                'pending': len(self.pending_txs),
                'created_at': self.created_at,
                'state_root': self.state_root[:16] + '...'
            }
    
    def create_block(self) -> Optional[Dict]:
        with self.lock:
            if not self.pending_txs:
                return None
            
            block = {
                'shard_id': self.shard_id,
                'block_id': len(self.blocks),
                'transactions': self.pending_txs.copy(),
                'tx_count': len(self.pending_txs),
                'total_amount': sum(tx.get('amount', 0) for tx in self.pending_txs),
                'timestamp': int(time.time()),
                'block_hash': hashlib.sha256(json.dumps(self.pending_txs).encode()).hexdigest()
            }
            
            self.blocks.append(block)
            self.pending_txs = []
            self.state_root = block['block_hash']
            return block

# ============================================================================
# ДИНАМИЧЕСКИЙ ШАРДИНГ
# ============================================================================

class DynamicSharding:
    def __init__(self, blockchain=None):
        self.blockchain = blockchain
        self.config = ShardingConfig()
        self.shards: Dict[int, Shard] = {}
        self.cross_shard_txs = []
        self.rebalancing = False
        self._running = False
        self.lock = threading.RLock()
        
        # Создаём начальные шарды
        for i in range(self.config.INITIAL_SHARDS):
            self.shards[i] = Shard(i)
        
        print(f"🗺️ Dynamic Sharding initialized with {self.config.INITIAL_SHARDS} shards")
    
    def get_shard_for_address(self, address: str) -> int:
        """Определение шарда для адреса"""
        hash_val = int(hashlib.md5(address.encode()).hexdigest()[:8], 16)
        active_shards = len(self.shards)
        return hash_val % active_shards
    
    def add_transaction(self, tx: Dict) -> int:
        """Добавление транзакции в соответствующий шард"""
        from_addr = tx.get('from', '')
        to_addr = tx.get('to', '')
        
        from_shard = self.get_shard_for_address(from_addr)
        to_shard = self.get_shard_for_address(to_addr)
        
        if from_shard == to_shard:
            shard = self.shards.get(from_shard)
            if shard:
                shard.add_transaction(tx)
                return from_shard
        else:
            tx['cross_shard'] = True
            tx['from_shard'] = from_shard
            tx['to_shard'] = to_shard
            
            with self.lock:
                self.cross_shard_txs.append(tx)
            
            from_shard_obj = self.shards.get(from_shard)
            to_shard_obj = self.shards.get(to_shard)
            
            if from_shard_obj:
                from_shard_obj.add_transaction(tx)
            if to_shard_obj:
                to_shard_obj.add_transaction(tx)
            
            return -1
        
        return -1
    
    def _check_and_rebalance(self):
        """Проверка нагрузки и ребалансировка"""
        if self.rebalancing:
            return
        
        loads = {}
        for shard_id, shard in self.shards.items():
            loads[shard_id] = shard.get_load()
        
        if not loads:
            return
        
        avg_load = sum(loads.values()) / len(loads)
        
        # Проверяем необходимость создания нового шарда
        if avg_load > self.config.TPS_THRESHOLD_HIGH and len(self.shards) < self.config.MAX_SHARDS:
            self._create_new_shard()
        
        # Проверяем необходимость объединения шардов
        low_shards = [sid for sid, load in loads.items() if load < self.config.TPS_THRESHOLD_LOW]
        if len(low_shards) > 1 and len(self.shards) > self.config.MIN_SHARDS:
            self._merge_shards(low_shards[:2])
    
    def _create_new_shard(self):
        """Создание нового шарда"""
        with self.lock:
            self.rebalancing = True
            try:
                new_id = max(self.shards.keys()) + 1
                new_shard = Shard(new_id)
                self.shards[new_id] = new_shard
                print(f"✅ New shard created: Shard #{new_id}")
                self._redistribute_load()
            finally:
                self.rebalancing = False
    
    def _merge_shards(self, shard_ids: List[int]):
        """Объединение шардов"""
        with self.lock:
            self.rebalancing = True
            try:
                shard_ids.sort()
                target_id = shard_ids[0]
                target_shard = self.shards[target_id]
                
                for sid in shard_ids[1:]:
                    source_shard = self.shards.get(sid)
                    if source_shard:
                        target_shard.transactions.extend(source_shard.transactions)
                        target_shard.tx_count += source_shard.tx_count
                        target_shard.total_volume += source_shard.total_volume
                        del self.shards[sid]
                        print(f"🗑️ Shard #{sid} merged into Shard #{target_id}")
                
                print(f"✅ Shards merged: {shard_ids} → {target_id}")
            finally:
                self.rebalancing = False
    
    def _redistribute_load(self):
        """Перераспределение нагрузки"""
        all_txs = []
        for shard in self.shards.values():
            all_txs.extend(shard.pending_txs)
            shard.pending_txs = []
        
        for tx in all_txs:
            from_addr = tx.get('from', '')
            shard_id = self.get_shard_for_address(from_addr)
            shard = self.shards.get(shard_id)
            if shard:
                shard.add_transaction(tx)
    
    def process_cross_shard_transactions(self):
        """Обработка межшардовых транзакций"""
        with self.lock:
            for tx in self.cross_shard_txs[:]:
                from_shard = self.shards.get(tx.get('from_shard'))
                to_shard = self.shards.get(tx.get('to_shard'))
                
                if from_shard and to_shard:
                    tx['status'] = 'confirmed'
                    tx['confirmed_at'] = int(time.time())
                    self.cross_shard_txs.remove(tx)
                    print(f"🔄 Cross-shard transaction confirmed")
    
    def start(self):
        """Запуск системы"""
        self._running = True
        
        def sharding_loop():
            while self._running:
                try:
                    self._check_and_rebalance()
                    self.process_cross_shard_transactions()
                except Exception as e:
                    print(f"⚠️ Sharding error: {e}")
                time.sleep(self.config.REBALANCE_INTERVAL)
        
        threading.Thread(target=sharding_loop, daemon=True).start()
        print(f"🚀 Dynamic Sharding started")
    
    def stop(self):
        self._running = False
    
    def get_stats(self) -> Dict:
        """Статистика"""
        total_txs = sum(s.tx_count for s in self.shards.values())
        total_volume = sum(s.total_volume for s in self.shards.values())
        avg_tps = sum(s.tps for s in self.shards.values()) / len(self.shards) if self.shards else 0
        
        return {
            'total_shards': len(self.shards),
            'min_shards': self.config.MIN_SHARDS,
            'max_shards': self.config.MAX_SHARDS,
            'total_transactions': total_txs,
            'total_volume': total_volume,
            'average_tps': round(avg_tps, 2),
            'cross_shard_pending': len(self.cross_shard_txs),
            'rebalancing': self.rebalancing,
            'shards': [s.get_stats() for s in self.shards.values()]
        }

sharding_manager = DynamicSharding()

def init_sharding(blockchain):
    global sharding_manager
    sharding_manager = DynamicSharding(blockchain)
    sharding_manager.start()
    return sharding_manager
