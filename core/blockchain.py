# core/blockchain.py
# ПОЛНОЕ ПРОМЫШЛЕННОЕ ЯДРО

import time
import threading
from typing import List, Dict, Optional

from core.block import Block
from core.transaction import Transaction, TX_COINBASE
from core.mempool import Mempool
from storage.rocksdb_storage import RocksDBStorage

class Blockchain:
    def __init__(self, data_dir: str = 'data/mainnet'):
        self.storage = RocksDBStorage(data_dir)
        self.mempool = Mempool()
        self.chain = []
        self._lock = threading.RLock()
        self._mining_lock = threading.Lock()
        self.difficulty = 1
        self._load_chain()
        
        print(f"\n✅ Blockchain инициализирован: {len(self.chain)} блоков")
    
    def _load_chain(self):
        height = self.storage.get_chain_height()
        if height > 0:
            for h in range(height + 1):
                block_data = self.storage.get_block(h)
                if block_data:
                    self.chain.append(Block.from_dict(block_data))
            print(f"   📦 Загружено {len(self.chain)} блоков")
        else:
            genesis = Block.genesis()
            self.chain.append(genesis)
            self.storage.save_block(genesis)
            self.storage.set_balance("foundation", 1000000000.0)
            print("   🌍 Создан генезис блок")
    
    def get_latest_block(self) -> Block:
        return self.chain[-1]
    
    def validate_block(self, block: Block, previous_block: Block) -> bool:
        """Полная валидация блока"""
        try:
            # 1. Проверка previous hash
            if block.previous_hash != previous_block.block_hash:
                print("❌ Invalid previous hash")
                return False
            
            # 2. Проверка merkle root
            calculated_merkle = block.calculate_merkle_root()
            if calculated_merkle != block.merkle_root:
                print("❌ Invalid merkle root")
                return False
            
            # 3. Проверка hash блока
            calculated_hash = block.calculate_hash()
            if calculated_hash != block.block_hash:
                print("❌ Invalid block hash")
                return False
            
            # 4. Проверка PoW
            if not block.block_hash.startswith("0" * self.difficulty):
                print("❌ Invalid proof of work")
                return False
            
            # 5. Проверка транзакций
            for tx in block.transactions:
                if not tx.verify():
                    print(f"❌ Invalid transaction signature: {tx.tx_hash}")
                    return False
            
            return True
        except Exception as e:
            print(f"❌ Block validation error: {e}")
            return False
    
    def add_transaction(self, tx: Transaction) -> bool:
        """Добавление транзакции в мемпул"""
        if tx.amount <= 0:
            return False
        
        if not tx.verify():
            return False
        
        balance = self.storage.get_balance(tx.from_addr)
        if balance < tx.amount + tx.fee:
            return False
        
        return self.mempool.add_transaction(tx)
    
    def mine_block(self, miner: str) -> Optional[Block]:
        """Майнинг блока"""
        with self._mining_lock:
            txs = self.mempool.get_transactions(limit=100)
            if not txs:
                return None
            
            # Валидация транзакций перед майнингом
            valid_txs = []
            for tx in txs:
                balance = self.storage.get_balance(tx.from_addr)
                if balance >= tx.amount + tx.fee:
                    valid_txs.append(tx)
                else:
                    self.mempool.remove_transaction(tx.tx_hash)
            
            if not valid_txs:
                return None
            
            previous = self.get_latest_block()
            block = Block(
                height=previous.height + 1,
                previous_hash=previous.block_hash,
                transactions=valid_txs,
                timestamp=int(time.time()),
                nonce=0,
                miner=miner,
                difficulty=self.difficulty
            )
            
            # PoW
            while not block.calculate_hash().startswith('0' * self.difficulty):
                block.nonce += 1
            block.block_hash = block.calculate_hash()
            
            # Валидация блока
            if not self.validate_block(block, previous):
                return None
            
            # Применение транзакций
            reward = 50
            self.storage.add_balance(miner, reward)
            
            for tx in valid_txs:
                if self.storage.transfer(tx.from_addr, tx.to_addr, tx.amount, tx.fee):
                    self.storage.save_transaction(tx)
                    self.mempool.remove_transaction(tx.tx_hash)
            
            self.storage.save_block(block)
            self.chain.append(block)
            
            print(f"⛏️ Блок #{block.height} добыт {miner} с {len(valid_txs)} транзакциями")
            print(f"   Merkle Root: {block.merkle_root[:32]}...")
            
            return block
    
    def get_balance(self, address: str) -> float:
        return self.storage.get_balance(address)
    
    def verify_chain(self) -> bool:
        """Полная верификация цепочки"""
        print("\n🔍 Верификация цепочки...")
        for i in range(1, len(self.chain)):
            if not self.validate_block(self.chain[i], self.chain[i-1]):
                return False
        print("✅ Цепочка верифицирована")
        return True
    
    def get_stats(self) -> Dict:
        latest = self.get_latest_block()
        return {
            'blocks': len(self.chain),
            'height': latest.height,
            'merkle_root': latest.merkle_root[:32] + "...",
            'difficulty': self.difficulty,
            'mempool_size': self.mempool.size()
        }
    
    def close(self):
        self.storage.close()
