#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN - SINGLE RUNTIME
Единственный источник запуска всей системы
"""

import sqlite3
import time
import hashlib
import threading
import json
import os
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# ============================================================
# 1. STORAGE (только данные)
# ============================================================

class Storage:
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

# ============================================================
# 2. MEMPOOL
# ============================================================

class Mempool:
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

# ============================================================
# 3. BLOCKCHAIN CORE (ЕДИНСТВЕННЫЙ)
# ============================================================

class Blockchain:
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
            print("[Blockchain] Genesis created")
    
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
        last = self.storage.get_last_block()
        if block["parent_hash"] != last["block_hash"]:
            return False
        if block["height"] != last["height"] + 1:
            return False
        
        for tx in block.get("txs", []):
            balance = self.storage.get_balance(tx["from"])
            if balance >= tx["value"]:
                self.storage.set_balance(tx["from"], balance - tx["value"])
                self.storage.set_balance(tx["to"], self.storage.get_balance(tx["to"]) + tx["value"])
                self.storage.increment_nonce(tx["from"])
        
        return self.storage.add_block(block)
    
    def submit_transaction(self, tx: Dict) -> bool:
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
# 4. CONSENSUS
# ============================================================

class Consensus:
    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain
    
    def validate_block(self, block: Dict) -> bool:
        last = self.blockchain.get_last_block()
        if block["parent_hash"] != last["block_hash"]:
            return False
        if block["height"] != last["height"] + 1:
            return False
        return True

# ============================================================
# 5. API (FLASK)
# ============================================================

class API:
    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain
        self.app = None
    
    def start(self):
        from flask import Flask, jsonify
        self.app = Flask(__name__)
        
        @self.app.route('/health')
        def health():
            return jsonify({"status": "ok", "height": self.blockchain.get_height()})
        
        @self.app.route('/balance/<address>')
        def balance(address):
            return jsonify({"address": address, "balance": self.blockchain.get_balance(address)})
        
        @self.app.route('/blocks')
        def blocks():
            return jsonify({"height": self.blockchain.get_height()})
        
        def run():
            self.app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
        
        threading.Thread(target=run, daemon=True).start()
        print("[API] Started on http://localhost:8080")

# ============================================================
# 6. P2P (упрощённая)
# ============================================================

class P2P:
    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain
    
    def start(self):
        print("[P2P] Started (simplified)")

# ============================================================
# 7. ЕДИНСТВЕННЫЙ RUNTIME (ОРКЕСТРАТОР)
# ============================================================

class Runtime:
    """Единственный оркестратор - владеет ВСЕМИ компонентами"""
    
    def __init__(self):
        # Только ОДИН экземпляр каждого компонента
        self.storage = Storage()
        self.mempool = Mempool()
        self.blockchain = Blockchain(self.storage, self.mempool)
        self.consensus = Consensus(self.blockchain)
        
        # Сервисы
        self.api = API(self.blockchain)
        self.p2p = P2P(self.blockchain)
        
        self.running = False
    
    def _mining_loop(self):
        while self.running:
            time.sleep(15)
            block = self.blockchain.create_block("miner")
            if self.consensus.validate_block(block):
                if self.blockchain.add_block(block):
                    print(f"[Miner] ⛏️ Block #{block['height']}: {block['block_hash'][:16]}...")
    
    def start(self):
        self.running = True
        
        # Запускаем сервисы
        self.api.start()
        self.p2p.start()
        
        # Запускаем майнинг
        mining_thread = threading.Thread(target=self._mining_loop, daemon=True)
        mining_thread.start()
        
        print("""
╔══════════════════════════════════════════════════════════════════╗
║     ABSOLUTE BLOCKCHAIN - SINGLE RUNTIME                        ║
║     ОДИН оркестратор | ОДИН blockchain | ВСЕ сервисы            ║
╚══════════════════════════════════════════════════════════════════╝
        """)
        print(f"   📦 Height: {self.blockchain.get_height()}")
        print(f"   💰 Balance (miner): {self.blockchain.get_balance('miner')}")
        print(f"   ⛏️ Mining: every 15 seconds")
        print(f"   🌐 API: http://localhost:8080")
        print("\n   Press Ctrl+C to stop\n")
    
    def stop(self):
        self.running = False

# ============================================================
# 8. ЗАПУСК (ТОЛЬКО ЗДЕСЬ!)
# ============================================================

if __name__ == "__main__":
    runtime = Runtime()
    try:
        runtime.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping runtime...")
        runtime.stop()
