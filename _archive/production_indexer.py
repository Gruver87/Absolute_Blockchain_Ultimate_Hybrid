#!/usr/bin/env python3
"""SINGLE WRITER INDEXER - единственный процесс, пишущий в БД"""

import json
import sqlite3
import urllib.request
import time
import threading
from queue import Queue

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"

block_queue = Queue()
stop_flag = False
db_lock = threading.Lock()

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

def get_node_height():
    h = rpc_call("eth_blockNumber", [])
    return int(h, 16) if h else 0

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

def process_block(height):
    block_data = rpc_call("eth_getBlockByNumber", [hex(height), True])
    if not block_data or not isinstance(block_data, dict):
        return False
    
    with db_lock:
        conn = get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("BEGIN")
            
            timestamp = int(block_data.get("timestamp", "0x0"), 16)
            miner = block_data.get("miner", "")
            transactions = block_data.get("transactions", [])
            
            cursor.execute('''
                INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, miner, tx_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (height, block_data.get("hash", ""), block_data.get("parentHash", ""),
                  timestamp, miner, len(transactions)))
            
            save_address(cursor, miner, timestamp)
            
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
            
            cursor.execute("COMMIT")
            return True
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            print(f"   ❌ Error: {e}")
            return False
        finally:
            conn.close()

def producer():
    last_queued = 0
    while not stop_flag:
        try:
            node_height = get_node_height()
            if node_height > last_queued:
                for h in range(last_queued + 1, node_height + 1):
                    block_queue.put(h)
                    print(f"📥 Queued block {h}")
                last_queued = node_height
            time.sleep(1)
        except:
            time.sleep(1)

def consumer():
    while not stop_flag:
        try:
            if not block_queue.empty():
                height = block_queue.get()
                print(f"📦 Processing block {height}...")
                if process_block(height):
                    print(f"   ✅ Block {height} indexed")
                else:
                    print(f"   ⚠️ Block {height} failed, queuing again")
                    block_queue.put(height)
            else:
                time.sleep(1)
        except:
            time.sleep(1)

def run():
    print("=" * 60)
    print("🚀 SINGLE WRITER INDEXER (Production)")
    print("=" * 60)
    
    threading.Thread(target=producer, daemon=True).start()
    threading.Thread(target=consumer, daemon=True).start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        global stop_flag
        stop_flag = True
        print("\n🛑 Indexer stopped")

if __name__ == "__main__":
    run()
