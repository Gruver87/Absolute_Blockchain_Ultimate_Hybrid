import sqlite3
import json
import time
import hashlib
import threading
import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================

@dataclass
class BlockchainConfig:
    db_path: str = "data/blockchain.db"
    p2p_port: int = 5000
    block_time: int = 15
    peers: List[str] = field(default_factory=list)

# ============================================================
# СОБЫТИЯ
# ============================================================

class EventType(Enum):
    BLOCK_ADDED = "block_added"
    TX_RECEIVED = "tx_received"

class EventBus:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.listeners = {}
        return cls._instance
    
    def emit(self, event: EventType, data: Any = None):
        for callback in self.listeners.get(event, []):
            try:
                callback(data)
            except:
                pass
    
    def on(self, event: EventType, callback):
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)

bus = EventBus()

# ============================================================
# STATE MANAGER (ЕДИНСТВЕННЫЙ ИСТОЧНИК ИСТИНЫ)
# ============================================================

class StateManager:
    def __init__(self, config: BlockchainConfig):
        self.config = config
        self._lock = threading.RLock()
        self._init_db()
        self._init_genesis()
    
    def _init_db(self):
        os.makedirs(os.path.dirname(self.config.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.config.db_path, check_same_thread=False)
        
        # Простая таблица блоков
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                height INTEGER PRIMARY KEY,
                block_hash TEXT UNIQUE,
                parent_hash TEXT,
                timestamp INTEGER,
                miner TEXT,
                tx_count INTEGER
            )
        """)
        
        # Таблица аккаунтов
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                address TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                nonce INTEGER DEFAULT 0
            )
        """)
        
        self.conn.commit()
    
    def _init_genesis(self):
        cursor = self.conn.execute("SELECT COUNT(*) FROM blocks")
        if cursor.fetchone()[0] == 0:
            genesis_hash = hashlib.sha256(b"genesis").hexdigest()
            self.conn.execute("""
                INSERT INTO blocks (height, block_hash, parent_hash, timestamp, miner, tx_count)
                VALUES (0, ?, ?, ?, ?, ?)
            """, (genesis_hash, "0"*64, int(time.time()), "genesis", 0))
            self.conn.commit()
            print("[StateManager] Genesis block created")
    
    def get_last_block(self) -> Optional[Dict]:
        with self._lock:
            cursor = self.conn.execute("SELECT * FROM blocks ORDER BY height DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return {"height": row[0], "block_hash": row[1], "parent_hash": row[2],
                       "timestamp": row[3], "miner": row[4], "tx_count": row[5]}
            return None
    
    def get_height(self) -> int:
        cursor = self.conn.execute("SELECT MAX(height) FROM blocks")
        row = cursor.fetchone()
        return row[0] if row[0] else 0
    
    def get_balance(self, address: str) -> int:
        cursor = self.conn.execute("SELECT balance FROM accounts WHERE address = ?", (address,))
        row = cursor.fetchone()
        return row[0] if row else 0
    
    def add_block(self, block: Dict) -> bool:
        """Добавляет блок - ТОЛЬКО через runtime"""
        with self._lock:
            try:
                # Проверка parent
                last = self.get_last_block()
                if last and block["parent_hash"] != last["block_hash"]:
                    return False
                
                self.conn.execute("""
                    INSERT INTO blocks (height, block_hash, parent_hash, timestamp, miner, tx_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (block["height"], block["block_hash"], block["parent_hash"],
                      block["timestamp"], block["miner"], block.get("tx_count", 0)))
                self.conn.commit()
                bus.emit(EventType.BLOCK_ADDED, block)
                return True
            except Exception as e:
                print(f"[StateManager] Error: {e}")
                return False

# ============================================================
# EXECUTION ENGINE
# ============================================================

class ExecutionEngine:
    def __init__(self, state: StateManager):
        self.state = state
        self.pending = []
    
    def create_block(self, miner: str) -> Dict:
        last = self.state.get_last_block()
        txs = self.pending[:10]
        
        block = {
            "height": last["height"] + 1 if last else 1,
            "parent_hash": last["block_hash"] if last else "0"*64,
            "timestamp": int(time.time()),
            "miner": miner,
            "tx_count": len(txs),
            "txs": txs
        }
        
        block_data = f"{block['height']}{block['parent_hash']}{block['timestamp']}{block['miner']}"
        block["block_hash"] = hashlib.sha256(block_data.encode()).hexdigest()
        
        return block
    
    def add_transaction(self, tx: Dict):
        self.pending.append(tx)
        bus.emit(EventType.TX_RECEIVED, tx)

# ============================================================
# КОНСЕНСУС
# ============================================================

class ConsensusEngine:
    def __init__(self, state: StateManager):
        self.state = state
    
    def validate_block(self, block: Dict) -> bool:
        last = self.state.get_last_block()
        if last and block["parent_hash"] != last["block_hash"]:
            return False
        if last and block["height"] != last["height"] + 1:
            return False
        return True

# ============================================================
# ЕДИНЫЙ RUNTIME
# ============================================================

class BlockchainRuntime:
    def __init__(self, config: BlockchainConfig):
        self.config = config
        self.state = StateManager(config)
        self.execution = ExecutionEngine(self.state)
        self.consensus = ConsensusEngine(self.state)
        self.running = False
        
        bus.on(EventType.BLOCK_ADDED, self._on_block)
    
    def _on_block(self, block):
        print(f"   ⛏️ Block #{block['height']}: {block['block_hash'][:16]}...")
    
    def _mining_loop(self):
        while self.running:
            time.sleep(self.config.block_time)
            block = self.execution.create_block(f"miner_{self.config.p2p_port}")
            if self.consensus.validate_block(block):
                if self.state.add_block(block):
                    pass
    
    def start(self):
        self.running = True
        
        mining_thread = threading.Thread(target=self._mining_loop, daemon=True)
        mining_thread.start()
        
        print("""
╔══════════════════════════════════════════════════════════════════╗
║     ABSOLUTE BLOCKCHAIN RUNTIME - STARTED                       ║
║     Single Source of Truth | Event-Driven                       ║
╚══════════════════════════════════════════════════════════════════╝
        """)
        print(f"   📦 Height: {self.state.get_height()}")
        print(f"   ⛏️ Mining: every {self.config.block_time} seconds\n")
    
    def stop(self):
        self.running = False

# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    
    config = BlockchainConfig(
        db_path="data/blockchain.db",
        block_time=15
    )
    
    runtime = BlockchainRuntime(config)
    
    try:
        runtime.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping runtime...")
        runtime.stop()
