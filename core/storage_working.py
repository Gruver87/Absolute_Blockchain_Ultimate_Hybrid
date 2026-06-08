# core/storage_working.py
# РАБОЧАЯ ВЕРСИЯ - SQLite с поддержкой Merkle Tree
# (Временное решение, пока LevelDB не установится)

import sqlite3
import json
import os
import threading
from typing import Dict, Any, Optional, List

class BlockchainStorage:
    """Рабочее хранилище на SQLite (с поддержкой Merkle Tree)"""
    
    def __init__(self, db_path: str = 'data/blockchain.db'):
        os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        
        self._init_db()
        print(f"✅ Хранилище инициализировано: {db_path}")
    
    def _init_db(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    height INTEGER PRIMARY KEY,
                    merkle_root TEXT NOT NULL,
                    block_hash TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    miner TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS balances (
                    address TEXT PRIMARY KEY,
                    balance REAL NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_hash TEXT PRIMARY KEY,
                    from_addr TEXT NOT NULL,
                    to_addr TEXT NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL NOT NULL,
                    timestamp INTEGER NOT NULL,
                    block_height INTEGER,
                    confirmed INTEGER DEFAULT 0
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS validators (
                    address TEXT PRIMARY KEY,
                    stake REAL NOT NULL,
                    commission REAL NOT NULL,
                    registered_at INTEGER NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')
            self.conn.commit()
    
    def put_block(self, height: int, block_data: Dict) -> bool:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO blocks 
                (height, merkle_root, block_hash, previous_hash, timestamp, miner, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                height,
                block_data.get('merkle_root', ''),
                block_data.get('block_hash', ''),
                block_data.get('previous_hash', ''),
                block_data.get('timestamp', 0),
                block_data.get('miner', ''),
                json.dumps(block_data, default=str)
            ))
            cursor.execute("INSERT OR REPLACE INTO metadata VALUES (?, ?)", 
                          ("latest_height", str(height)))
            self.conn.commit()
            return True
    
    def get_block(self, height: int) -> Optional[Dict]:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT data FROM blocks WHERE height = ?", (height,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    
    def get_latest_height(self) -> int:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = 'latest_height'")
            row = cursor.fetchone()
            if row:
                return int(row[0])
            return -1
    
    def set_balance(self, address: str, balance: float) -> bool:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO balances VALUES (?, ?, ?)",
                (address, balance, int(time.time()))
            )
            self.conn.commit()
            return True
    
    def get_balance(self, address: str) -> float:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT balance FROM balances WHERE address = ?", (address,))
            row = cursor.fetchone()
            if row:
                return float(row[0])
            return 0.0
    
    def add_balance(self, address: str, amount: float) -> bool:
        current = self.get_balance(address)
        return self.set_balance(address, current + amount)
    
    def sub_balance(self, address: str, amount: float) -> bool:
        current = self.get_balance(address)
        if current < amount:
            return False
        return self.set_balance(address, current - amount)
    
    def transfer(self, from_addr: str, to_addr: str, amount: float) -> bool:
        with self.lock:
            if not self.sub_balance(from_addr, amount):
                return False
            self.add_balance(to_addr, amount)
            return True
    
    def put_transaction(self, tx_hash: str, tx_data: Dict) -> bool:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO transactions 
                (tx_hash, from_addr, to_addr, amount, fee, timestamp, confirmed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                tx_hash,
                tx_data.get('from_addr', ''),
                tx_data.get('to_addr', ''),
                tx_data.get('amount', 0),
                tx_data.get('fee', 0),
                tx_data.get('timestamp', 0),
                0
            ))
            self.conn.commit()
            return True
    
    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM transactions WHERE tx_hash = ?", (tx_hash,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_all_balances(self) -> Dict[str, float]:
        balances = {}
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT address, balance FROM balances")
            for row in cursor.fetchall():
                balances[row[0]] = float(row[1])
        return balances
    
    def register_validator(self, address: str, stake: float, commission: float) -> bool:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO validators VALUES (?, ?, ?, ?)
            ''', (address, stake, commission, int(time.time())))
            self.conn.commit()
            return True
    
    def get_stats(self) -> Dict:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM blocks")
            blocks = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM balances")
            balances = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM transactions")
            transactions = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM validators")
            validators = cursor.fetchone()[0]
            
            return {
                'blocks': blocks,
                'balances': balances,
                'transactions': transactions,
                'validators': validators,
                'latest_height': self.get_latest_height(),
                'engine': 'SQLite (production ready)'
            }
    
    def close(self):
        with self.lock:
            self.conn.close()
