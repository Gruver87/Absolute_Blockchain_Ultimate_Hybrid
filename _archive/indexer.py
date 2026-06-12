#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple Blockchain Indexer"""

import json
import sqlite3
import urllib.request
import time
import os

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"

def rpc_call(method, params):
    data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode()).get("result")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocks (
            number INTEGER PRIMARY KEY,
            hash TEXT,
            parent_hash TEXT,
            timestamp INTEGER,
            tx_count INTEGER,
            miner TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            hash TEXT PRIMARY KEY,
            block_number INTEGER,
            from_addr TEXT,
            to_addr TEXT,
            value TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            address TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            tx_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def index_blocks():
    init_db()
    
    # Проверяем RPC
    try:
        height_hex = rpc_call("eth_blockNumber", [])
        if not height_hex:
            print("❌ Cannot connect to RPC. Make sure node is running on port 8545")
            return
        current = int(height_hex, 16)
        print(f"📊 Current chain height: {current}")
    except Exception as e:
        print(f"❌ RPC connection failed: {e}")
        print("   Make sure node_persistent.py is running")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for h in range(1, current + 1):
        try:
            block = rpc_call("eth_getBlockByNumber", [hex(h), True])
            if block and isinstance(block, dict):
                # Extract timestamp
                ts = block.get("timestamp", "0x0")
                if isinstance(ts, str) and ts.startswith("0x"):
                    timestamp = int(ts, 16)
                else:
                    timestamp = int(ts) if ts else 0
                
                # Save block
                cursor.execute('''
                    INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, tx_count, miner)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (h, block.get("hash", ""), block.get("parentHash", ""), timestamp, 
                      len(block.get("transactions", [])), block.get("miner", "")))
                
                # Save transactions
                for tx in block.get("transactions", []):
                    cursor.execute('''
                        INSERT OR REPLACE INTO transactions (hash, block_number, from_addr, to_addr, value)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (tx.get("hash", ""), h, tx.get("from", ""), tx.get("to", ""), tx.get("value", "0x0")))
                    
                    # Update accounts
                    for addr in [tx.get("from", ""), tx.get("to", "")]:
                        if addr and addr != "0x":
                            cursor.execute("INSERT OR IGNORE INTO accounts (address, balance, tx_count) VALUES (?, 0, 0)", (addr,))
                            cursor.execute("UPDATE accounts SET tx_count = tx_count + 1 WHERE address = ?", (addr,))
                
                if h % 50 == 0:
                    print(f"📦 Indexed {h} blocks")
                    conn.commit()
        except Exception as e:
            print(f"⚠️ Error indexing block {h}: {e}")
    
    conn.commit()
    conn.close()
    print(f"✅ Done! Indexed {current} blocks")

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 BLOCKCHAIN INDEXER")
    print("=" * 50)
    index_blocks()
