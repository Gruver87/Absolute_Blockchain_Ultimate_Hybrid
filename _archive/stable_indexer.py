#!/usr/bin/env python3
"""Stable Indexer - WAL mode, retry on lock"""

import json
import sqlite3
import urllib.request
import time
import os

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def rpc_call(method, params):
    for attempt in range(3):
        try:
            data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode()).get("result")
        except:
            time.sleep(1)
    return None

def index_blocks():
    # Получаем высоту
    height_hex = rpc_call("eth_blockNumber", [])
    if not height_hex:
        print("❌ Cannot connect to RPC")
        return
    
    current = int(height_hex, 16)
    print(f"📊 Chain height: {current}")
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # Проверяем последний блок в БД
    cursor.execute("SELECT MAX(number) FROM blocks")
    last = cursor.fetchone()[0] or 0
    print(f"📦 Last indexed: {last}")
    
    if last >= current:
        print("✅ Already up to date")
        conn.close()
        return
    
    print(f"🚀 Indexing {current - last} blocks...")
    
    for h in range(last + 1, current + 1):
        for retry in range(3):
            try:
                block = rpc_call("eth_getBlockByNumber", [hex(h), True])
                if block and isinstance(block, dict):
                    ts = block.get("timestamp", "0x0")
                    if isinstance(ts, str) and ts.startswith("0x"):
                        timestamp = int(ts, 16)
                    else:
                        timestamp = int(ts) if ts else 0
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, tx_count, miner)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (h, block.get("hash", ""), block.get("parentHash", ""), timestamp, 
                          len(block.get("transactions", [])), block.get("miner", "")))
                    
                    for tx in block.get("transactions", []):
                        cursor.execute('''
                            INSERT OR REPLACE INTO transactions (hash, block_number, from_addr, to_addr, value)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (tx.get("hash", ""), h, tx.get("from", ""), tx.get("to", ""), tx.get("value", "0x0")))
                    
                    conn.commit()
                    
                    if h % 50 == 0:
                        print(f"   📦 Indexed {h} blocks")
                    break
            except sqlite3.OperationalError as e:
                if "locked" in str(e):
                    print(f"   ⏳ Database locked, retrying block {h}...")
                    time.sleep(1)
                    continue
                else:
                    print(f"   ❌ Error: {e}")
                    break
            except Exception as e:
                print(f"   ❌ Error at block {h}: {e}")
                break
    
    conn.close()
    print(f"✅ Done! Indexed up to block {current}")

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 STABLE INDEXER (WAL MODE)")
    print("=" * 50)
    index_blocks()
