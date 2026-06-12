#!/usr/bin/env python3
"""BATCH INDEXER - ускоренная индексация (50 блоков за раз)"""

import json
import sqlite3
import urllib.request
import time

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"
BATCH_SIZE = 50

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

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

def save_address(cursor, address, timestamp):
    if not address or address == "0x" or len(address) < 10:
        return
    cursor.execute('''
        INSERT OR IGNORE INTO addresses (address, balance, tx_count, first_seen, last_seen)
        VALUES (?, 0, 0, ?, ?)
    ''', (address, timestamp, timestamp))
    cursor.execute('''
        UPDATE addresses SET tx_count = tx_count + 1, last_seen = ?
        WHERE address = ?
    ''', (timestamp, address))

def process_block(cursor, height, block_data):
    timestamp = int(block_data.get("timestamp", "0x0"), 16)
    miner = block_data.get("miner", "")
    transactions = block_data.get("transactions", [])
    
    # Сохраняем блок
    cursor.execute('''
        INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, miner, tx_count)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (height, block_data.get("hash", ""), block_data.get("parentHash", ""),
          timestamp, miner, len(transactions)))
    
    # Сохраняем майнера
    save_address(cursor, miner, timestamp)
    
    # Сохраняем транзакции
    for tx in transactions:
        tx_hash = tx.get("hash", "")
        from_addr = tx.get("from", "")
        to_addr = tx.get("to", "")
        value = tx.get("value", "0x0")
        
        save_address(cursor, from_addr, timestamp)
        save_address(cursor, to_addr, timestamp)
        
        cursor.execute('''
            INSERT OR REPLACE INTO transactions
            (hash, block_number, from_addr, to_addr, value, gas_price, gas_used, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tx_hash, height, from_addr, to_addr, value, "0x1", 21000, 1, timestamp))

def run():
    print("=" * 60)
    print("🚀 BATCH INDEXER (50 блоков за раз)")
    print("=" * 60)
    
    conn = get_conn()
    cursor = conn.cursor()
    
    while True:
        try:
            # Текущая высота ноды
            height_hex = rpc_call("eth_blockNumber", [])
            if not height_hex:
                time.sleep(2)
                continue
            node_height = int(height_hex, 16)
            
            # Текущая высота БД
            cursor.execute("SELECT MAX(number) FROM blocks")
            db_height = cursor.fetchone()[0] or 0
            
            if db_height >= node_height:
                print(f"📊 Synced! Node: {node_height} | DB: {db_height}")
                time.sleep(5)
                continue
            
            # Индексируем батч
            batch_end = min(db_height + BATCH_SIZE, node_height)
            print(f"📦 Indexing blocks {db_height + 1} to {batch_end}...")
            
            conn.execute("BEGIN")
            
            for height in range(db_height + 1, batch_end + 1):
                block_data = rpc_call("eth_getBlockByNumber", [hex(height), True])
                if block_data and isinstance(block_data, dict):
                    process_block(cursor, height, block_data)
            
            conn.commit()
            print(f"   ✅ Indexed up to block {batch_end}")
            
            time.sleep(0.5)
            
        except KeyboardInterrupt:
            print("\n🛑 Indexer stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            conn.rollback()
            time.sleep(2)

if __name__ == "__main__":
    run()
