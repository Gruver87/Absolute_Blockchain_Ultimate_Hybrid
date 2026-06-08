#!/usr/bin/env python3
"""SIMPLE WORKING INDEXER - сохраняет адреса и газ"""

import json
import sqlite3
import urllib.request
import time

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # Таблица блоков
    c.execute('''
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
    
    # Таблица транзакций
    c.execute('''
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
    
    # Таблица адресов
    c.execute('''
        CREATE TABLE IF NOT EXISTS addresses (
            address TEXT PRIMARY KEY,
            balance TEXT,
            tx_count INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database ready")

def rpc_call(method, params):
    try:
        data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
        req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode()).get("result")
    except:
        return None

def update_address(address, timestamp):
    if not address or address == "0x":
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO addresses (address, balance, tx_count)
        VALUES (?, 0, 0)
    ''', (address,))
    c.execute('''
        UPDATE addresses SET tx_count = tx_count + 1
        WHERE address = ?
    ''', (address,))
    conn.commit()
    conn.close()

def index_block(height):
    block_data = rpc_call("eth_getBlockByNumber", [hex(height), True])
    if not block_data or not isinstance(block_data, dict):
        return False
    
    timestamp = int(block_data.get("timestamp", "0x0"), 16)
    miner = block_data.get("miner", "")
    transactions = block_data.get("transactions", [])
    block_gas = 0
    
    conn = get_conn()
    c = conn.cursor()
    
    # Сохраняем блок
    c.execute('''
        INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, miner, tx_count, gas_used)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (height, block_data.get("hash", ""), block_data.get("parentHash", ""),
          timestamp, miner, len(transactions), block_gas))
    
    # Сохраняем транзакции и адреса
    for tx in transactions:
        tx_hash = tx.get("hash", "")
        from_addr = tx.get("from", "")
        to_addr = tx.get("to", "")
        value = tx.get("value", "0x0")
        
        # Обновляем адреса
        update_address(from_addr, timestamp)
        update_address(to_addr, timestamp)
        
        # Сохраняем транзакцию
        c.execute('''
            INSERT OR REPLACE INTO transactions
            (hash, block_number, from_addr, to_addr, value, gas_price, gas_used, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tx_hash, height, from_addr, to_addr, value, "0x1", 21000, 1, timestamp))
    
    conn.commit()
    conn.close()
    return True

def run():
    print("=" * 50)
    print("🚀 SIMPLE WORKING INDEXER")
    print("=" * 50)
    
    init_db()
    
    while True:
        try:
            height_hex = rpc_call("eth_blockNumber", [])
            if not height_hex:
                time.sleep(2)
                continue
            
            node_height = int(height_hex, 16)
            
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT MAX(number) FROM blocks")
            db_height = c.fetchone()[0] or 0
            conn.close()
            
            if db_height >= node_height:
                print(f"📊 Synced! Height: {node_height}")
                time.sleep(5)
                continue
            
            height = db_height + 1
            print(f"📦 Indexing block {height}...")
            
            if index_block(height):
                print(f"   ✅ Block {height} indexed")
            else:
                print(f"   ⚠️ Block {height} failed")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n🛑 Indexer stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    run()
