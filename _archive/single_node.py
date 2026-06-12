import sqlite3
import time
import hashlib
import threading
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# ============================================================
# 1. ЕДИНОЕ ХРАНИЛИЩЕ (только данные)
# ============================================================

class Storage:
    """Только хранение данных - НЕ логика"""
    
    def __init__(self, db_path: str = "data/chain.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                height INTEGER PRIMARY KEY,
                block_hash TEXT UNIQUE,
                parent_hash TEXT,
                timestamp INTEGER,
                miner TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                address TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                nonce INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS nfts (
                token_id TEXT PRIMARY KEY,
                owner TEXT,
                name TEXT,
                metadata TEXT
            )
        """)
        self.conn.commit()
    
    def get_last_block(self):
        cursor = self.conn.execute("SELECT * FROM blocks ORDER BY height DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return {"height": row[0], "block_hash": row[1], "parent_hash": row[2], "timestamp": row[3], "miner": row[4]}
        return None
    
    def add_block(self, block: Dict) -> bool:
        try:
            self.conn.execute("INSERT INTO blocks VALUES (?, ?, ?, ?, ?)",
                             (block["height"], block["block_hash"], block["parent_hash"], block["timestamp"], block["miner"]))
            self.conn.commit()
            return True
        except:
            return False
    
    def get_balance(self, address: str) -> int:
        cursor = self.conn.execute("SELECT balance FROM accounts WHERE address = ?", (address,))
        row = cursor.fetchone()
        return row[0] if row else 0
    
    def set_balance(self, address: str, balance: int):
        self.conn.execute("INSERT OR REPLACE INTO accounts (address, balance, nonce) VALUES (?, ?, COALESCE((SELECT nonce FROM accounts WHERE address = ?), 0))",
                         (address, balance, address))
        self.conn.commit()
    
    def get_nonce(self, address: str) -> int:
        cursor = self.conn.execute("SELECT nonce FROM accounts WHERE address = ?", (address,))
        row = cursor.fetchone()
        return row[0] if row else 0
    
    def increment_nonce(self, address: str):
        self.conn.execute("UPDATE accounts SET nonce = nonce + 1 WHERE address = ?", (address,))
        self.conn.commit()
    
    def add_nft(self, token_id: str, owner: str, name: str, metadata: str):
        self.conn.execute("INSERT OR REPLACE INTO nfts VALUES (?, ?, ?, ?)", (token_id, owner, name, metadata))
        self.conn.commit()
    
    def get_nfts(self, owner: str = None) -> List[Dict]:
        if owner:
            cursor = self.conn.execute("SELECT * FROM nfts WHERE owner = ?", (owner,))
        else:
            cursor = self.conn.execute("SELECT * FROM nfts")
        return [{"token_id": r[0], "owner": r[1], "name": r[2], "metadata": r[3]} for r in cursor.fetchall()]

# ============================================================
# 2. ЕДИНЫЙ МЕМПУЛ
# ============================================================

class Mempool:
    """Единый пул транзакций"""
    
    def __init__(self):
        self.transactions = []
        self.lock = threading.RLock()
    
    def add(self, tx: Dict):
        with self.lock:
            self.transactions.append(tx)
    
    def get_batch(self, limit: int = 10) -> List[Dict]:
        with self.lock:
            batch = self.transactions[:limit]
            self.transactions = self.transactions[limit:]
            return batch
    
    def size(self) -> int:
        return len(self.transactions)

# ============================================================
# 3. ЕДИНЫЙ БЛОКЧЕЙН (СЕРДЦЕ СИСТЕМЫ)
# ============================================================

class Blockchain:
    """ЕДИНСТВЕННЫЙ источник истины"""
    
    def __init__(self, storage: Storage, mempool: Mempool):
        self.storage = storage
        self.mempool = mempool
        self._init_genesis()
    
    def _init_genesis(self):
        if self.storage.get_last_block() is None:
            genesis_hash = hashlib.sha256(b"genesis").hexdigest()
            self.storage.add_block({
                "height": 0,
                "block_hash": genesis_hash,
                "parent_hash": "0"*64,
                "timestamp": int(time.time()),
                "miner": "genesis"
            })
            print("[Blockchain] Genesis block created")
    
    def get_height(self) -> int:
        block = self.storage.get_last_block()
        return block["height"] if block else 0
    
    def get_last_block(self) -> Dict:
        return self.storage.get_last_block()
    
    def create_block(self, miner: str) -> Dict:
        last = self.storage.get_last_block()
        txs = self.mempool.get_batch(10)
        
        block = {
            "height": last["height"] + 1,
            "parent_hash": last["block_hash"],
            "timestamp": int(time.time()),
            "miner": miner,
            "txs": txs
        }
        
        block_data = f"{block['height']}{block['parent_hash']}{block['timestamp']}{block['miner']}"
        block["block_hash"] = hashlib.sha256(block_data.encode()).hexdigest()
        
        return block
    
    def add_block(self, block: Dict) -> bool:
        # Валидация
        last = self.storage.get_last_block()
        if block["parent_hash"] != last["block_hash"]:
            return False
        if block["height"] != last["height"] + 1:
            return False
        
        # Применяем транзакции
        for tx in block.get("txs", []):
            # Проверяем баланс
            balance = self.storage.get_balance(tx["from"])
            if balance >= tx["value"]:
                self.storage.set_balance(tx["from"], balance - tx["value"])
                self.storage.set_balance(tx["to"], self.storage.get_balance(tx["to"]) + tx["value"])
                self.storage.increment_nonce(tx["from"])
        
        # Сохраняем блок
        return self.storage.add_block(block)
    
    def submit_transaction(self, tx: Dict) -> bool:
        # Базовая проверка
        balance = self.storage.get_balance(tx["from"])
        nonce = self.storage.get_nonce(tx["from"])
        
        if balance < tx["value"]:
            return False
        if tx["nonce"] != nonce:
            return False
        
        self.mempool.add(tx)
        return True
    
    def get_balance(self, address: str) -> int:
        return self.storage.get_balance(address)

# ============================================================
# 4. ПЛАГИНЫ (НЕ ИМЕЮТ СВОЕГО STATE!)
# ============================================================

class NFTPlugin:
    """NFT - работает через единый blockchain"""
    
    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain
    
    def mint(self, owner: str, name: str, metadata: str) -> str:
        token_id = hashlib.sha256(f"{owner}{name}{time.time()}".encode()).hexdigest()[:16]
        self.blockchain.storage.add_nft(token_id, owner, name, metadata)
        return token_id
    
    def get_collection(self, owner: str = None) -> List[Dict]:
        return self.blockchain.storage.get_nfts(owner)

class EVMPlugin:
    """EVM - работает через единый blockchain"""
    
    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain
    
    def execute(self, code: bytes, sender: str) -> Dict:
        # Упрощённая EVM
        return {"success": True, "result": "executed"}

class OraclesPlugin:
    """Oracles - внешние данные"""
    
    def get_price(self, symbol: str) -> float:
        # Симуляция цен
        prices = {"btc": 50000, "eth": 3000, "sol": 100}
        return prices.get(symbol.lower(), 0)

# ============================================================
# 5. ЕДИНЫЙ RUNTIME (ОРКЕСТРАТОР)
# ============================================================

class Runtime:
    """Единый оркестратор - владеет ВСЕМИ компонентами"""
    
    def __init__(self):
        # Только ОДИН экземпляр каждого компонента
        self.storage = Storage()
        self.mempool = Mempool()
        self.blockchain = Blockchain(self.storage, self.mempool)
        
        # Плагины - получают доступ к единому blockchain
        self.nft = NFTPlugin(self.blockchain)
        self.evm = EVMPlugin(self.blockchain)
        self.oracles = OraclesPlugin()
        
        self.running = False
    
    def _mining_loop(self):
        """Майнинг - пишет в единый blockchain"""
        while self.running:
            time.sleep(15)
            block = self.blockchain.create_block("miner")
            if self.blockchain.add_block(block):
                print(f"[Miner] ⛏️ Block #{block['height']}: {block['block_hash'][:16]}...")
    
    def start(self):
        self.running = True
        
        mining_thread = threading.Thread(target=self._mining_loop, daemon=True)
        mining_thread.start()
        
        print("""
╔══════════════════════════════════════════════════════════════════╗
║     ABSOLUTE BLOCKCHAIN - SINGLE NODE                           ║
║     ОДИН blockchain | ОДИН mempool | Плагины без state          ║
╚══════════════════════════════════════════════════════════════════╝
        """)
        print(f"   📦 Height: {self.blockchain.get_height()}")
        print(f"   💰 Balance: {self.blockchain.get_balance('miner')}")
        print(f"   ⛏️ Mining: every 15 seconds\n")
    
    def stop(self):
        self.running = False

# ============================================================
# 6. ЗАПУСК
# ============================================================

if __name__ == "__main__":
    runtime = Runtime()
    
    try:
        runtime.start()
        
        # Демо: создаём NFT через 30 секунд
        def demo_nft():
            time.sleep(30)
            token = runtime.nft.mint("miner", "Genesis NFT", "https://example.com/nft.png")
            print(f"[Demo] NFT minted: {token}")
        
        demo_thread = threading.Thread(target=demo_nft, daemon=True)
        demo_thread.start()
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        runtime.stop()
