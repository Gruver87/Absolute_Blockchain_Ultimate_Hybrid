#!/usr/bin/env python3
"""Fast Indexer - догоняет ноду с WAL режимом"""

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
                time.sleep(1)
            else:
                print(f"   ⚠️ RPC error: {e}")
                return None
    return None

# Получаем текущую высоту
height_hex = rpc_call("eth_blockNumber", [])
if not height_hex:
    print("❌ Cannot connect to RPC")
    exit(1)

current = int(height_hex, 16)
print(f"📊 Node height: {current}")

conn = get_conn()
c = conn.cursor()

# Находим последний блок в БД
c.execute("SELECT MAX(number) FROM blocks")
last_in_db = c.fetchone()[0] or 0
print(f"📦 Last block in DB: {last_in_db}")

if last_in_db >= current:
    print("✅ Already up to date!")
    conn.close()
    exit(0)

print(f"🚀 Indexing blocks {last_in_db + 1} to {current}...")

for h in range(last_in_db + 1, current + 1):
    for retry in range(3):
        try:
            block = rpc_call("eth_getBlockByNumber", [hex(h), True])
            if block and isinstance(block, dict):
                # Parse timestamp
                ts = block.get("timestamp", "0x0")
                if isinstance(ts, str) and ts.startswith("0x"):
                    timestamp = int(ts, 16)
                else:
                    timestamp = int(ts) if ts else 0
                
                # Save block
                c.execute('''
                    INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, tx_count, miner)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (h, block.get("hash", ""), block.get("parentHash", ""), timestamp,
                      len(block.get("transactions", [])), block.get("miner", "")))
                
                # Save transactions
                for tx in block.get("transactions", []):
                    c.execute('''
                        INSERT OR REPLACE INTO transactions (hash, block_number, from_addr, to_addr, value)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (tx.get("hash", ""), h, tx.get("from", ""), tx.get("to", ""), tx.get("value", "0x0")))
                
                conn.commit()
                
                if h % 50 == 0:
                    print(f"   📦 Indexed up to block {h}")
                break
            else:
                print(f"   ⚠️ Block {h} not found, retrying...")
                time.sleep(1)
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                print(f"   ⏳ Database locked, retrying block {h}...")
                time.sleep(1)
            else:
                print(f"   ❌ SQL error: {e}")
                break
        except Exception as e:
            print(f"   ❌ Error at block {h}: {e}")
            break

conn.close()
print(f"✅ Done! Indexed up to block {current}")
print(f"📊 Final DB block count: {current}")
