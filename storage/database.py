# storage/database.py (fixed)
"""
SQLite Database Manager for Blockchain
"""

import sqlite3
import json
import os
import time
import threading
from typing import Dict, List, Optional, Any
from contextlib import contextmanager


class BlockchainDB:
    """SQLite database for blockchain persistence"""
    
    def __init__(self, db_path: str = "data/blockchain.db"):
        self.db_path = db_path
        self.lock = threading.RLock()
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Blocks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    hash TEXT PRIMARY KEY,
                    number INTEGER UNIQUE NOT NULL,
                    parent_hash TEXT,
                    timestamp INTEGER,
                    proposer TEXT,
                    state_root TEXT,
                    tx_root TEXT,
                    signature TEXT,
                    public_key TEXT,
                    block_data TEXT,
                    is_canonical INTEGER DEFAULT 1,
                    created_at INTEGER
                )
            ''')
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_number ON blocks(number)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_parent ON blocks(parent_hash)')
            
            # Accounts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    address TEXT PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    nonce INTEGER DEFAULT 0,
                    code_hash TEXT DEFAULT "",
                    updated_at INTEGER
                )
            ''')
            
            # Validators table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS validators (
                    address TEXT PRIMARY KEY,
                    stake INTEGER DEFAULT 0,
                    commission INTEGER DEFAULT 5,
                    registered_at INTEGER,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    hash TEXT PRIMARY KEY,
                    from_addr TEXT,
                    to_addr TEXT,
                    value INTEGER,
                    nonce INTEGER,
                    signature TEXT,
                    block_hash TEXT,
                    block_number INTEGER,
                    status INTEGER DEFAULT 1,
                    gas_used INTEGER DEFAULT 21000,
                    logs TEXT,
                    timestamp INTEGER
                )
            ''')
            
            # Attestations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS attestations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    validator TEXT,
                    target_hash TEXT,
                    target_height INTEGER,
                    slot INTEGER,
                    signature TEXT,
                    created_at INTEGER
                )
            ''')
            
            # Metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at INTEGER
                )
            ''')
            
            # Checkpoints table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS checkpoints (
                    hash TEXT PRIMARY KEY,
                    height INTEGER,
                    snapshot_data TEXT,
                    created_at INTEGER
                )
            ''')
            
            conn.commit()
            
            # Initialize metadata if empty
            cursor.execute("SELECT COUNT(*) FROM metadata")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO metadata (key, value) VALUES ('version', '47')")
                cursor.execute("INSERT INTO metadata (key, value) VALUES ('chain_id', '1')")
                conn.commit()
    
    @contextmanager
    def get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def save_block(self, block: dict) -> bool:
        """Save block to database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO blocks 
                (hash, number, parent_hash, timestamp, proposer, state_root, tx_root, 
                 signature, public_key, block_data, is_canonical, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                block.get("hash"),
                block.get("number"),
                block.get("parent_hash"),
                block.get("timestamp"),
                block.get("proposer"),
                block.get("state_root"),
                block.get("tx_root"),
                block.get("signature"),
                block.get("public_key"),
                json.dumps(block),
                1,
                int(time.time())
            ))
            conn.commit()
            return True
    
    def get_block(self, block_hash: str) -> Optional[dict]:
        """Get block by hash"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT block_data FROM blocks WHERE hash = ?", (block_hash,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    
    def get_block_by_number(self, number: int) -> Optional[dict]:
        """Get block by number"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT block_data FROM blocks WHERE number = ?", (number,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    
    def get_latest_block(self) -> Optional[dict]:
        """Get latest canonical block"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT block_data FROM blocks 
                WHERE is_canonical = 1 
                ORDER BY number DESC LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    
    def get_latest_block_number(self) -> int:
        """Get latest block number"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT MAX(number) as max_num FROM blocks WHERE is_canonical = 1
            ''')
            row = cursor.fetchone()
            return row[0] if row and row[0] else 0
    
    def save_account(self, address: str, balance: int, nonce: int = 0) -> bool:
        """Save account state"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO accounts (address, balance, nonce, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (address, balance, nonce, int(time.time())))
            conn.commit()
            return True
    
    def get_account(self, address: str) -> Optional[dict]:
        """Get account state"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE address = ?", (address,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_balance(self, address: str) -> int:
        """Get account balance"""
        account = self.get_account(address)
        return account["balance"] if account else 0
    
    def save_validator(self, address: str, stake: int) -> bool:
        """Save validator info"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO validators (address, stake, registered_at)
                VALUES (?, ?, ?)
            ''', (address, stake, int(time.time())))
            conn.commit()
            return True
    
    def get_validators(self) -> List[dict]:
        """Get all validators"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM validators WHERE is_active = 1")
            return [dict(row) for row in cursor.fetchall()]
    
    def save_transaction_receipt(self, tx_hash: str, receipt: dict) -> bool:
        """Save transaction receipt"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO transactions 
                (hash, from_addr, to_addr, value, nonce, signature, 
                 block_hash, block_number, status, gas_used, logs, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tx_hash,
                receipt.get("from"),
                receipt.get("to"),
                receipt.get("value"),
                receipt.get("nonce"),
                receipt.get("signature"),
                receipt.get("block_hash"),
                receipt.get("block_number"),
                receipt.get("status", 1),
                receipt.get("gas_used", 21000),
                json.dumps(receipt.get("logs", [])),
                int(time.time())
            ))
            conn.commit()
            return True
    
    def save_metadata(self, key: str, value: str) -> bool:
        """Save metadata"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO metadata (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, value, int(time.time())))
            conn.commit()
            return True
    
    def get_metadata(self, key: str) -> Optional[str]:
        """Get metadata"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def save_checkpoint(self, block_hash: str, height: int, snapshot: dict) -> bool:
        """Save state checkpoint"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO checkpoints (hash, height, snapshot_data, created_at)
                VALUES (?, ?, ?, ?)
            ''', (block_hash, height, json.dumps(snapshot), int(time.time())))
            conn.commit()
            return True
    
    def get_latest_checkpoint(self) -> Optional[dict]:
        """Get latest checkpoint"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM checkpoints ORDER BY height DESC LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                return {
                    "hash": row[0],
                    "height": row[1],
                    "snapshot": json.loads(row[2])
                }
            return None
    
    def get_stats(self) -> dict:
        """Get database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM blocks")
            blocks = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM accounts")
            accounts = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM transactions")
            txs = cursor.fetchone()[0]
            
            return {
                "total_blocks": blocks,
                "total_accounts": accounts,
                "total_transactions": txs,
                "latest_block": self.get_latest_block_number(),
                "db_path": self.db_path
            }
