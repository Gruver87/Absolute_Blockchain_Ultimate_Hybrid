#!/usr/bin/env python3
"""PRODUCTION INDEXER - WAL mode, batch processing, no locks"""

import json
import sqlite3
import urllib.request
import time
import os
from datetime import datetime

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"
BATCH_SIZE = 20  # Обрабатываем по 20 блоков за раз

def get_conn():
    """Создание соединения с БД с оптимизированными настройками"""
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn

def rpc_call(method, params, retries=3):
    """RPC вызов с retry"""
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
                return None
    return None

def fetch_block(height):
    """Получение блока с защитой"""
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
        "tx_count": len(block.get("transactions", [])),
        "miner": block.get("miner", ""),
        "transactions": block.get("transactions", [])
    }

def init_db():
    """Инициализация БД с правильными индексами"""
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocks (
            number INTEGER PRIMARY KEY,
            hash TEXT,
            parent_hash TEXT,
            timestamp INTEGER,
            tx_count INTEGER,
            miner TEXT,
            indexed_at INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            hash TEXT PRIMARY KEY,
            block_number INTEGER,
            from_addr TEXT,
            to_addr TEXT,
            value TEXT,
            FOREIGN KEY (block_number) REFERENCES blocks(number)
        )
    ''')
    
    # Индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_number ON blocks(number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_timestamp ON blocks(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_addr)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_addr)')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized (WAL mode + indexes)")

def get_db_height():
    """Текущая высота в БД"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(number) FROM blocks")
    result = cursor.fetchone()[0] or 0
    conn.close()
    return result

def get_node_height():
    """Высота ноды из RPC"""
    height_hex = rpc_call("eth_blockNumber", [])
    if height_hex:
        return int(height_hex, 16)
    return 0

def save_blocks_batch(blocks):
    """Пакетное сохранение блоков"""
    if not blocks:
        return
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # Пакетная вставка блоков
    block_data = [(b["number"], b["hash"], b["parent_hash"], b["timestamp"], 
                   b["tx_count"], b["miner"], int(time.time())) for b in blocks]
    cursor.executemany('''
        INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, tx_count, miner, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', block_data)
    
    # Пакетная вставка транзакций
    tx_data = []
    for b in blocks:
        for tx in b.get("transactions", []):
            tx_data.append((tx.get("hash", ""), b["number"], 
                           tx.get("from", ""), tx.get("to", ""), 
                           tx.get("value", "0x0")))
    
    if tx_data:
        cursor.executemany('''
            INSERT OR REPLACE INTO transactions (hash, block_number, from_addr, to_addr, value)
            VALUES (?, ?, ?, ?, ?)
        ''', tx_data)
    
    conn.commit()
    conn.close()

def run_indexer():
    """Основной цикл индексатора"""
    print("=" * 60)
    print("🚀 PRODUCTION INDEXER (WAL + BATCH)")
    print("=" * 60)
    
    init_db()
    
    while True:
        try:
            node_height = get_node_height()
            db_height = get_db_height()
            lag = node_height - db_height
            
            if lag == 0:
                print(f"📊 Synced! Height: {node_height}")
                time.sleep(5)
                continue
            
            # Показываем прогресс
            print(f"📊 Node: {node_height} | DB: {db_height} | Lag: {lag}")
            
            # Определяем сколько блоков индексировать
            batch_end = min(db_height + BATCH_SIZE, node_height)
            blocks_to_index = batch_end - db_height
            
            if blocks_to_index <= 0:
                time.sleep(5)
                continue
            
            print(f"🚀 Indexing blocks {db_height + 1} to {batch_end} ({blocks_to_index} blocks)...")
            
            # Собираем батч блоков
            blocks = []
            for height in range(db_height + 1, batch_end + 1):
                block = fetch_block(height)
                if block:
                    blocks.append(block)
                else:
                    print(f"   ⚠️ Block {height} not found")
            
            # Сохраняем батч
            if blocks:
                save_blocks_batch(blocks)
                print(f"   ✅ Saved {len(blocks)} blocks")
            
            # Небольшая пауза между батчами
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n🛑 Indexer stopped")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_indexer()
