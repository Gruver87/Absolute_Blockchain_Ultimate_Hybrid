#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production Indexer - исправленная версия"""

import json
import sqlite3
import urllib.request
import time
import os
import sys
from collections import deque

# Настройка кодировки для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"
BATCH_SIZE = 25

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    # Читаем схему с правильной кодировкой
    with open("etherscan_schema.sql", "r", encoding="utf-8") as f:
        schema = f.read()
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.executescript(schema)
    conn.commit()
    conn.close()
    print("✅ Database initialized with UTF-8 schema")

def rpc_call(method, params, retries=3):
    for attempt in range(retries):
        try:
            data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode()).get("result")
        except:
            if attempt < retries - 1:
                time.sleep(0.5)
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
        "gas_limit": 0,
        "size": 0,
        "nonce": block.get("nonce", ""),
        "difficulty": block.get("difficulty", "0x0"),
        "indexed_at": int(time.time()),
        "transactions": block.get("transactions", [])
    }

def save_batch(blocks):
    if not blocks:
        return
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # Сохраняем блоки
    block_data = [(b["number"], b["hash"], b["parent_hash"], b["timestamp"], 
                   b["miner"], b["tx_count"], b["gas_used"], b["gas_limit"], 
                   b["size"], b["nonce"], b["difficulty"], b["indexed_at"]) for b in blocks]
    cursor.executemany('''
        INSERT OR REPLACE INTO blocks 
        (number, hash, parent_hash, timestamp, miner, tx_count, gas_used, gas_limit, size, nonce, difficulty, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', block_data)
    
    conn.commit()
    conn.close()

def run_indexer():
    print("=" * 60)
    print("🚀 PRODUCTION INDEXER (FIXED UTF-8)")
    print("=" * 60)
    
    # Удаляем старую БД для чистого старта
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("📁 Old database removed")
    
    init_db()
    
    while True:
        try:
            # Получаем высоту ноды
            height_hex = rpc_call("eth_blockNumber", [])
            if not height_hex:
                print("❌ Cannot connect to RPC")
                time.sleep(5)
                continue
            
            node_height = int(height_hex, 16)
            
            # Получаем высоту БД
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(number) FROM blocks")
            db_height = cursor.fetchone()[0] or 0
            conn.close()
            
            lag = node_height - db_height
            
            if lag == 0:
                print(f"📊 Synced! Height: {node_height}")
                time.sleep(5)
                continue
            
            print(f"📊 Node: {node_height} | DB: {db_height} | Lag: {lag}")
            
            # Индексируем новые блоки
            batch_end = min(db_height + BATCH_SIZE, node_height)
            
            if batch_end <= db_height:
                time.sleep(2)
                continue
            
            print(f"🚀 Indexing blocks {db_height + 1} to {batch_end}...")
            
            blocks = []
            for height in range(db_height + 1, batch_end + 1):
                block = fetch_block(height)
                if block:
                    blocks.append(block)
            
            if blocks:
                save_batch(blocks)
                print(f"   ✅ Saved {len(blocks)} blocks")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n🛑 Indexer stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_indexer()
