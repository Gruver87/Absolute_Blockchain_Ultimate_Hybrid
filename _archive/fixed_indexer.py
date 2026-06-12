#!/usr/bin/env python3
"""FIXED INDEXER - одна транзакция на блок, WAL mode"""

import json
import sqlite3
import urllib.request
import time

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def rpc_call(method, params, retries=3):
    for attempt in range(retries):
        try:
            data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode()).get("result")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.5)
            else:
                print(f"   RPC error: {e}")
                return None
    return None

def index_block(cursor, height, block_data):
    """Индексация блока с одним курсором (без новых соединений)"""
    
    timestamp = int(block_data.get("timestamp", "0x0"), 16)
    miner = block_data.get("miner", "")
    transactions = block_data.get("transactions", [])
    
    # Сохраняем блок
    cursor.execute('''
        INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, miner, tx_count)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (height, block_data.get("hash", ""), block_data.get("parentHash", ""),
          timestamp, miner, len(transactions)))
    
    # Сохраняем майнера как адрес (через тот же курсор)
    if miner and miner != "0x" and len(miner) > 10:
        cursor.execute('''
            INSERT OR IGNORE INTO addresses (address, balance, tx_count, first_seen, last_seen)
            VALUES (?, 0, 0, ?, ?)
        ''', (miner, timestamp, timestamp))
        cursor.execute('''
            UPDATE addresses SET tx_count = tx_count + 1, last_seen = ?
            WHERE address = ?
        ''', (timestamp, miner))
    
    # Сохраняем транзакции и адреса
    for tx in transactions:
        tx_hash = tx.get("hash", "")
        from_addr = tx.get("from", "")
        to_addr = tx.get("to", "")
        value = tx.get("value", "0x0")
        
        # Сохраняем адреса (через тот же курсор)
        for addr in [from_addr, to_addr]:
            if addr and addr != "0x" and len(addr) > 10:
                cursor.execute('''
                    INSERT OR IGNORE INTO addresses (address, balance, tx_count, first_seen, last_seen)
                    VALUES (?, 0, 0, ?, ?)
                ''', (addr, timestamp, timestamp))
                cursor.execute('''
                    UPDATE addresses SET tx_count = tx_count + 1, last_seen = ?
                    WHERE address = ?
                ''', (timestamp, addr))
        
        # Сохраняем транзакцию
        cursor.execute('''
            INSERT OR REPLACE INTO transactions
            (hash, block_number, from_addr, to_addr, value, gas_price, gas_used, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tx_hash, height, from_addr, to_addr, value, "0x1", 21000, 1, timestamp))
    
    return len(transactions)

def get_node_height():
    h = rpc_call("eth_blockNumber", [])
    return int(h, 16) if h else 0

def get_db_height(cursor):
    cursor.execute("SELECT MAX(number) FROM blocks")
    result = cursor.fetchone()[0] or 0
    return result

def run():
    print("=" * 60)
    print("🚀 FIXED INDEXER (одна транзакция на блок)")
    print("=" * 60)
    
    conn = get_conn()
    cursor = conn.cursor()
    
    while True:
        try:
            node_height = get_node_height()
            db_height = get_db_height(cursor)
            
            if db_height >= node_height:
                print(f"📊 Synced! Height: {node_height}")
                time.sleep(5)
                continue
            
            height = db_height + 1
            print(f"📦 Indexing block {height}...")
            
            # Начинаем транзакцию
            conn.execute("BEGIN")
            
            block_data = rpc_call("eth_getBlockByNumber", [hex(height), True])
            if block_data and isinstance(block_data, dict):
                tx_count = index_block(cursor, height, block_data)
                conn.commit()
                print(f"   ✅ Block {height} done | Txs: {tx_count}")
            else:
                conn.rollback()
                print(f"   ⚠️ Block {height} not found, skipping")
            
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
