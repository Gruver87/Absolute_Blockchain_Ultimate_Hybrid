# core/blockchain_rocks.py
# БЛОКЧЕЙН ЯДРО НА ROCKSDB - ИСПРАВЛЕННАЯ ВЕРСИЯ

import time
import threading
from typing import List, Dict, Optional

from core.block import Block
from core.transaction import Transaction, TX_TRANSFER, TX_GENESIS, TX_COINBASE
from core.merkle import MerkleTree
from core.tx_signer import TransactionSigner
from storage.rocksdb_storage import RocksDBStorage
from core.mempool import Mempool

class BlockchainRocks:
    def __init__(self, data_dir: str = 'data/mainnet_rocks'):
        self.storage = RocksDBStorage(f"{data_dir}")
        self.mempool = Mempool(max_size=100000)
        self.chain = []
        self._lock = threading.RLock()
        self._mining_lock = threading.Lock()
        
        self._load_chain()
        
        print(f"\n✅ Blockchain Rocks инициализирован:")
        print(f"   Блоков: {len(self.chain)}")
        print(f"   Хранилище: RocksDB")
        print(f"   Путь: {data_dir}")
    
    def _load_chain(self):
        height = self.storage.get_chain_height()
        
        if height > 0:
            blocks = self.storage.iter_blocks(0, height)
            for block_data in blocks:
                self.chain.append(Block.from_dict(block_data))
            print(f"   📦 Загружено {len(self.chain)} блоков из RocksDB")
        else:
            genesis = Block.genesis()
            genesis.block_hash = genesis.calculate_hash()
            self.chain.append(genesis)
            self.storage.save_block(genesis)
            self.storage.set_balance("foundation", 1000000000.0)
            self.storage.set_balance("staking_pool", 0.0)
            print("   🌍 Создан генезис блок в RocksDB")
    
    def get_latest_block(self) -> Optional[Block]:
        if self.chain:
            block_data = self.chain[-1]
            if isinstance(block_data, dict):
                return Block.from_dict(block_data)
            return block_data
        return None
    
    def get_block_by_height(self, height: int) -> Optional[Block]:
        if 0 <= height < len(self.chain):
            block_data = self.chain[height]
            if isinstance(block_data, dict):
                return Block.from_dict(block_data)
            return block_data
        block_data = self.storage.get_block(height)
        if block_data:
            return Block.from_dict(block_data)
        return None
    
    def add_transaction(self, tx: Transaction) -> bool:
        if tx.amount <= 0 and tx.tx_type not in [TX_GENESIS, TX_COINBASE]:
            return False
        
        if not tx.verify():
            return False
        
        balance = self.storage.get_balance(tx.from_addr)
        if balance < tx.amount + tx.gas_price:
            return False
        
        return self.mempool.add(tx)
    
    def mine_block(self, miner: str) -> Optional[Block]:
        with self._mining_lock:
            txs = self.mempool.get_transactions(limit=1000)
            if not txs:
                return None
            
            valid_txs = []
            for tx in txs:
                if self.storage.get_balance(tx.from_addr) >= tx.amount + tx.gas_price:
                    valid_txs.append(tx)
                else:
                    self.mempool.remove(tx.tx_hash)
            
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
                difficulty=1
            )
            
            # PoW
            while not block.calculate_hash().startswith('0' * block.difficulty):
                block.nonce += 1
            block.block_hash = block.calculate_hash()
            
            if not block.verify():
                return None
            
            # Применяем транзакции
            reward = 50
            self.storage.add_balance(miner, reward)
            
            for tx in valid_txs:
                if self.storage.transfer(tx.from_addr, tx.to_addr, tx.amount, tx.gas_price):
                    self.storage.save_transaction(tx)
                    self.mempool.remove(tx.tx_hash)
            
            self.storage.save_block(block)
            self.chain.append(block)
            
            print(f"⛏️ Блок #{block.height} добыт {miner} с {len(valid_txs)} транзакциями")
            print(f"   Merkle Root: {block.merkle_root[:32]}...")
            
            return block
    
    def get_balance(self, address: str) -> float:
        return self.storage.get_balance(address)
    
    def verify_chain(self) -> bool:
        print("\n🔍 Верификация цепочки...")
        for i, block_data in enumerate(self.chain):
            block = block_data if isinstance(block_data, Block) else Block.from_dict(block_data)
            if i > 0:
                prev = self.chain[i-1] if isinstance(self.chain[i-1], Block) else Block.from_dict(self.chain[i-1])
                if block.previous_hash != prev.block_hash:
                    print(f"❌ Ошибка связи блоков #{i}")
                    return False
            if not block.verify():
                print(f"❌ Блок #{i} не прошёл верификацию")
                return False
        print("✅ Вся цепочка верифицирована")
        return True
    
    def get_stats(self) -> Dict:
        latest = self.get_latest_block()
        total_supply = 0
        for addr in ['foundation', 'staking_pool']:
            total_supply += self.storage.get_balance(addr)
        
        return {
            'network': 'Absolute Blockchain',
            'version': '16.0',
            'engine': 'RocksDB',
            'blocks': len(self.chain),
            'height': latest.height if latest else 0,
            'merkle_root': latest.merkle_root[:32] + "..." if latest else "none",
            'total_supply': total_supply,
            'mempool_size': self.mempool.size(),
            'storage_stats': self.storage.get_stats()
        }
    
    def get_peers(self) -> List[str]:
        return ["127.0.0.1:5000", "127.0.0.1:5001", "127.0.0.1:5002"]
    
    def close(self):
        self.storage.close()
