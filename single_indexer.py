#!/usr/bin/env python3
"""SINGLE INDEXER - только один процесс!"""

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
    return conn

def rpc_call(method, params):
    for attempt in range(3):
        try:
            data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode()).get("result")
        except:
            if attempt < 2:
                time.sleep(0.5)
    return None

def save_address(address, timestamp):
    if not address or address == "0x" or len(address) < 10:
        return
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute('''
            INSERT OR IGNORE INTO addresses (address, balance, tx_count, first_seen, last_seen)
            VALUES (?, 0, 0, ?, ?)
        ''', (address, timestamp, timestamp))
        c.execute('''
            UPDATE addresses SET tx_count = tx_count + 1, last_seen = ?
            WHERE address = ?
        ''', (timestamp, address))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"      ⚠️ Address error: {e}")

def run():
    print("=" * 60)
    print("🚀 SINGLE INDEXER (один процесс, WAL mode)")
    print("=" * 60)
    
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
            
            block_data = rpc_call("eth_getBlockByNumber", [hex(height), True])
            if block_data and isinstance(block_data, dict):
                timestamp = int(block_data.get("timestamp", "0x0"), 16)
                miner = block_data.get("miner", "")
                transactions = block_data.get("transactions", [])
                
                conn = get_conn()
                c = conn.cursor()
                
                # Сохраняем блок
                c.execute('''
                    INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, miner, tx_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (height, block_data.get("hash", ""), block_data.get("parentHash", ""),
                      timestamp, miner, len(transactions)))
                
                # Сохраняем майнера
                save_address(miner, timestamp)
                
                # Сохраняем транзакции
                for tx in transactions:
                    tx_hash = tx.get("hash", "")
                    from_addr = tx.get("from", "")
                    to_addr = tx.get("to", "")
                    value = tx.get("value", "0x0")
                    
                    save_address(from_addr, timestamp)
                    save_address(to_addr, timestamp)
                    
                    c.execute('''
                        INSERT OR REPLACE INTO transactions
                        (hash, block_number, from_addr, to_addr, value, gas_price, gas_used, status, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (tx_hash, height, from_addr, to_addr, value, "0x1", 21000, 1, timestamp))
                
                conn.commit()
                conn.close()
                print(f"   ✅ Block {height} done. Txs: {len(transactions)}")
            else:
                print(f"   ⚠️ Block {height} not found")
            
            time.sleep(0.5)
            
        except KeyboardInterrupt:
            print("\n🛑 Indexer stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    run()
