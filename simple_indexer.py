#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIMPLE INDEXER - один блок за раз, без батчей"""

import json
import sqlite3
import urllib.request
import time
import os

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    with open("final_schema.sql", "r", encoding="utf-8") as f:
        schema = f.read()
    conn = get_conn()
    conn.executescript(schema)
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

def get_node_height():
    h = rpc_call("eth_blockNumber", [])
    return int(h, 16) if h else 0

def get_db_height():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT MAX(number) FROM blocks")
    result = c.fetchone()[0] or 0
    conn.close()
    return result

def save_block(block):
    if not block:
        return
    
    conn = get_conn()
    c = conn.cursor()
    
    c.execute('''
        INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, miner, tx_count)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (block["number"], block["hash"], block["parent_hash"], 
          block["timestamp"], block["miner"], len(block.get("transactions", []))))
    
    for tx in block.get("transactions", []):
        c.execute('''
            INSERT OR REPLACE INTO transactions (hash, block_number, from_addr, to_addr, value, gas, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (tx.get("hash", ""), block["number"], 
              tx.get("from", ""), tx.get("to", ""), 
              tx.get("value", "0"), 21000, block["timestamp"]))
    
    conn.commit()
    conn.close()

def run_indexer():
    print("=" * 60)
    print("📦 SIMPLE INDEXER (один блок за раз)")
    print("=" * 60)
    
    init_db()
    
    while True:
        try:
            node_h = get_node_height()
            db_h = get_db_height()
            
            if db_h < node_h:
                height = db_h + 1
                print(f"📦 Indexing block {height}...")
                
                block_data = rpc_call("eth_getBlockByNumber", [hex(height), True])
                if block_data and isinstance(block_data, dict):
                    block = {
                        "number": int(block_data.get("number", "0x0"), 16),
                        "hash": block_data.get("hash", ""),
                        "parent_hash": block_data.get("parentHash", ""),
                        "timestamp": int(block_data.get("timestamp", "0x0"), 16),
                        "miner": block_data.get("miner", ""),
                        "transactions": block_data.get("transactions", [])
                    }
                    save_block(block)
                    print(f"   ✅ Block {height} saved")
                else:
                    print(f"   ⚠️ Block {height} not found")
            else:
                if node_h > 0:
                    print(f"📊 Synced! Height: {node_h}")
                time.sleep(2)
        
        except KeyboardInterrupt:
            print("\n🛑 Indexer stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    run_indexer()
