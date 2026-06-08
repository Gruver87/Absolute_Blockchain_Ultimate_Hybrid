#!/usr/bin/env python3
"""Simple Indexer - заполняет БД"""

import json
import sqlite3
import urllib.request
import time

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"

def rpc_call(method, params):
    try:
        data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
        req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode()).get("result")
    except:
        return None

# Получаем высоту
height_hex = rpc_call("eth_blockNumber", [])
current = int(height_hex, 16)
print(f"📊 Node height: {current}")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Индексируем блоки
for h in range(1, current + 1):
    block = rpc_call("eth_getBlockByNumber", [hex(h), True])
    if block:
        ts = block.get("timestamp", "0x0")
        if isinstance(ts, str) and ts.startswith("0x"):
            timestamp = int(ts, 16)
        else:
            timestamp = int(ts) if ts else 0
        
        c.execute('INSERT OR REPLACE INTO blocks VALUES (?, ?, ?, ?, ?, ?)',
                  (h, block.get("hash", ""), block.get("parentHash", ""), timestamp,
                   len(block.get("transactions", [])), block.get("miner", "")))
        
        if h % 50 == 0:
            print(f"📦 Indexed {h} blocks")
            conn.commit()

conn.commit()
conn.close()
print(f"✅ Done! Indexed {current} blocks")
