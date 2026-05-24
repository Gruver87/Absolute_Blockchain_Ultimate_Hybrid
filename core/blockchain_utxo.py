# core/blockchain_utxo.py
# БЛОКЧЕЙН ЯДРО С UTXO

import time
import threading
from typing import List, Dict, Optional

from core.block import Block
from core.utxo import UTXO
from core.utxo_set import UTXOSet
from core.tx_builder import TransactionBuilder
from storage.rocksdb_storage import RocksDBStorage

class BlockchainUTXO:
    def __init__(self, data_dir: str = 'data/mainnet_utxo'):
        self.storage = RocksDBStorage(data_dir)
        self.utxo_set = UTXOSet(f"{data_dir}_utxo")
        self.chain = []
        self._mining_lock = threading.Lock()
        self.difficulty = 1
        self._load_chain()
        print(f"✅ Blockchain UTXO инициализирован: {len(self.chain)} блоков")
    
    def _load_chain(self):
        height = self.storage.get_chain_height()
        if height > 0:
            for h in range(height + 1):
                block_data = self.storage.get_block(h)
                if block_data:
                    self.chain.append(Block.from_dict(block_data))
        else:
            genesis = Block.genesis()
            self.chain.append(genesis)
            self.storage.save_block(genesis)
            # Добавляем UTXO
            genesis_utxo = UTXO(
                tx_hash=genesis.transactions[0].tx_hash,
                output_index=0,
                owner="foundation",
                amount=1000000000.0
            )
            self.utxo_set.add_utxo(genesis_utxo)
            print("   🌍 Создан генезис блок")
    
    def get_latest_block(self):
        return self.chain[-1]
    
    def get_balance(self, address: str) -> float:
        return self.utxo_set.get_balance(address)
    
    def get_stats(self):
        latest = self.get_latest_block()
        utxo_stats = {'total_utxos': 0, 'unspent_utxos': 0, 'total_amount': 0}
        try:
            utxo_stats = self.utxo_set.get_stats()
        except:
            pass
        
        return {
            'blocks': len(self.chain),
            'height': latest.height,
            'merkle_root': latest.merkle_root[:32] + "...",
            'mempool_size': 0,
            'difficulty': self.difficulty,
            'utxo_stats': utxo_stats
        }
    
    def has_block(self, block_hash: str) -> bool:
        for block in self.chain:
            b_hash = block.block_hash if hasattr(block, 'block_hash') else block.get('block_hash')
            if b_hash == block_hash:
                return True
        return False
    
    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        for block in self.chain:
            b_hash = block.block_hash if hasattr(block, 'block_hash') else block.get('block_hash')
            if b_hash == block_hash:
                return block
        return None
    
    def add_external_block(self, block_data: dict):
        try:
            block = Block.from_dict(block_data)
            latest = self.get_latest_block()
            
            if block.previous_hash == latest.block_hash:
                self.chain.append(block)
                self.storage.save_block(block)
                print(f"   ✅ Блок #{block.height} добавлен")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
    
    def get_chain(self) -> List:
        return self.chain
    
    def close(self):
        self.storage.close()
        self.utxo_set.close()
