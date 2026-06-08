#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FAST INDEXER - догоняет ноду батчами по 100 блоков"""

import json
import sqlite3
import urllib.request
import time
import os

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"
BATCH_SIZE = 100

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocks (
            number INTEGER PRIMARY KEY,
            hash TEXT,
            parent_hash TEXT,
            timestamp INTEGER,
            miner TEXT,
            tx_count INTEGER,
            gas_used INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            hash TEXT PRIMARY KEY,
            block_number INTEGER,
            from_addr TEXT,
            to_addr TEXT,
            value TEXT,
            gas_price TEXT,
            gas_used INTEGER,
            status INTEGER,
            timestamp INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            address TEXT PRIMARY KEY,
            balance TEXT,
            tx_count INTEGER
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def rpc_call(method, params):
    try:
        data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
        req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode()).get("result")
    except:
        return None

def fetch_block(height):
    block = rpc_call("eth_getBlockByNumber", [hex(height), True])
    if not block or not isinstance(block, dict):
        return None
    
    ts = block.get("timestamp", "0x0")
    if isinstance(ts, str) and ts.startswith("0x"):
        timestamp = int(ts, 16)
    else:
        timestamp = int(ts) if ts else 0
    
    return {
        "number": height,
        "hash": block.get("hash", ""),
        "parent_hash": block.get("parentHash", ""),
        "timestamp": timestamp,
        "miner": block.get("miner", ""),
        "tx_count": len(block.get("transactions", [])),
        "gas_used": 0,
        "transactions": block.get("transactions", [])
    }

def save_blocks_batch(blocks):
    if not blocks:
        return
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # Сохраняем блоки
    for b in blocks:
        cursor.execute('''
            INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, miner, tx_count, gas_used)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (b["number"], b["hash"], b["parent_hash"], b["timestamp"], 
              b["miner"], b["tx_count"], b["gas_used"]))
        
        # Сохраняем транзакции
        for tx in b.get("transactions", []):
            cursor.execute('''
                INSERT OR REPLACE INTO transactions (hash, block_number, from_addr, to_addr, value, gas_price, gas_used, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (tx.get("hash", ""), b["number"], tx.get("from", ""), tx.get("to", ""),
                  tx.get("value", "0"), tx.get("gasPrice", "0x1"), 21000, 1, b["timestamp"]))
    
    conn.commit()
    conn.close()

def run():
    print("=" * 60)
    print("🚀 FAST INDEXER (BATCH MODE)")
    print("=" * 60)
    
    init_db()
    
    # Получаем текущую высоту ноды
    height_hex = rpc_call("eth_blockNumber", [])
    if not height_hex:
        print("❌ Cannot connect to RPC")
        return
    
    node_height = int(height_hex, 16)
    print(f"📊 Node height: {node_height}")
    
    # Получаем текущую высоту БД
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(number) FROM blocks")
    db_height = cursor.fetchone()[0] or 0
    conn.close()
    
    print(f"📦 DB height: {db_height}")
    
    if db_height >= node_height:
        print("✅ Already synced!")
        return
    
    print(f"🚀 Indexing {node_height - db_height} blocks...")
    
    for batch_start in range(db_height + 1, node_height + 1, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE - 1, node_height)
        print(f"   📦 Batch {batch_start}-{batch_end}...")
        
        blocks = []
        for height in range(batch_start, batch_end + 1):
            block = fetch_block(height)
            if block:
                blocks.append(block)
        
        if blocks:
            save_blocks_batch(blocks)
            print(f"      ✅ Saved {len(blocks)} blocks")
        
        time.sleep(0.5)
    
    print(f"✅ Done! Indexed up to block {node_height}")

if __name__ == "__main__":
    run()
