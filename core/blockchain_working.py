# core/blockchain_working.py
# РАБОЧАЯ ВЕРСИЯ БЛОКЧЕЙН ЯДРА

import time
from typing import List, Dict, Optional
from core.block import Block, Transaction
from core.merkle import MerkleTree
from core.storage_working import BlockchainStorage
from core.locks import mempool, locks, rate_limiter

class BlockchainCore:
    def __init__(self, data_dir: str = 'data'):
        self.chain: List[Block] = []
        self.mempool = mempool
        self.storage = BlockchainStorage(f"{data_dir}/blockchain.db")
        self.locks = locks
        self._load_chain()
        print(f"✅ Blockchain Core инициализирован: {len(self.chain)} блоков")
    
    def _load_chain(self):
        latest = self.storage.get_latest_height()
        if latest >= 0:
            for height in range(0, latest + 1):
                block_data = self.storage.get_block(height)
                if block_data:
                    self.chain.append(Block.from_dict(block_data))
        else:
            from core.block import Block
            genesis = Block.genesis()
            genesis.block_hash = genesis.calculate_hash()
            self.chain.append(genesis)
            self.storage.put_block(0, genesis.to_dict())
            self.storage.set_balance("foundation", 1000000000.0)
    
    def get_latest_block(self) -> Block:
        return self.chain[-1]
    
    def add_transaction(self, tx: Transaction) -> bool:
        with self.locks.mempool_lock:
            balance = self.storage.get_balance(tx.from_addr)
            total = tx.amount + tx.fee
            if balance < total:
                return False
            return self.mempool.add(tx)
    
    def mine_block(self, miner: str) -> Optional[Block]:
        with self.locks.mining_lock:
            txs = self.mempool.get_all(limit=100)
            if not txs:
                return None
            
            previous = self.get_latest_block()
            block = Block(
                height=previous.height + 1,
                previous_hash=previous.block_hash,
                transactions=txs,
                timestamp=int(time.time()),
                nonce=0,
                miner=miner,
                difficulty=1
            )
            
            while True:
                block.block_hash = block.calculate_hash()
                if block.block_hash.startswith('0' * block.difficulty):
                    break
                block.nonce += 1
            
            if not block.verify():
                return None
            
            with self.locks.state_lock:
                reward = 50
                self.storage.add_balance(miner, reward)
                for tx in txs:
                    if self.storage.transfer(tx.from_addr, tx.to_addr, tx.amount):
                        self.storage.sub_balance(tx.from_addr, tx.fee)
                        self.storage.add_balance(miner, tx.fee)
                        self.storage.put_transaction(tx.tx_hash, tx.to_dict())
                        self.mempool.remove(tx.tx_hash)
            
            self.storage.put_block(block.height, block.to_dict())
            self.chain.append(block)
            print(f"⛏️ Блок #{block.height} добыт {miner} с {len(txs)} транзакциями")
            return block
    
    def get_balance(self, address: str) -> float:
        return self.storage.get_balance(address)
    
    def verify_chain(self) -> bool:
        for i, block in enumerate(self.chain):
            if i > 0 and block.previous_hash != self.chain[i-1].block_hash:
                print(f"❌ Ошибка связи блоков #{i}")
                return False
            if not block.verify():
                print(f"❌ Блок #{i} не прошёл верификацию")
                return False
        print("✅ Вся цепочка верифицирована")
        return True
    
    def get_stats(self) -> Dict:
        return {
            'blocks': len(self.chain),
            'height': self.get_latest_block().height,
            'mempool_size': self.mempool.size(),
            'storage_stats': self.storage.get_stats(),
            'total_supply': sum(self.storage.get_all_balances().values())
        }
    
    def close(self):
        self.storage.close()
