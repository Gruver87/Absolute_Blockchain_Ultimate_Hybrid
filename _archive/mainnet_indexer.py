#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mainnet Indexer - Адаптивный индексатор блокчейна (FIXED)"""

import json
import time
import sqlite3
import urllib.request
import urllib.error
import os
import sys
from datetime import datetime

# Фикс кодировки для Windows
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"
MAX_RETRIES = 3
RETRY_DELAY = 0.5

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Инициализация базы данных из schema.sql (с правильной кодировкой)"""
    if not os.path.exists("schema.sql"):
        print("❌ schema.sql not found!")
        return
    
    # Читаем файл в UTF-8
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema = f.read()
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.executescript(schema)
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def safe_rpc_call(method, params, retries=MAX_RETRIES):
    """Безопасный RPC вызов с retry"""
    for attempt in range(retries):
        try:
            data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                return result.get("result")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"RPC failed: {method} - {e}")
                return None
    return None

def index_block(height):
    """Индексация блока в БД"""
    print(f"📦 Indexing block {height}...")
    
    # Получаем блок
    block = safe_rpc_call("eth_getBlockByNumber", [hex(height), True])
    if not block or not isinstance(block, dict):
        print(f"   ⚠️ Block {height} not found or invalid format")
        return False
    
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # Извлекаем данные
        block_hash = block.get("hash", "")
        parent_hash = block.get("parentHash", "")
        timestamp = int(block.get("timestamp", "0x0"), 16)
        tx_count = len(block.get("transactions", []))
        miner = block.get("miner", "")
        gas_used = int(block.get("gasUsed", "0x0"), 16)
        gas_limit = int(block.get("gasLimit", "0x0"), 16)
        size = int(block.get("size", "0x0"), 16)
        nonce = block.get("nonce", "")
        difficulty = block.get("difficulty", "0x0")
        
        # Сохраняем блок
        cursor.execute('''
            INSERT OR REPLACE INTO blocks 
            (number, hash, parent_hash, timestamp, tx_count, miner, difficulty, gas_used, gas_limit, size, nonce, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (height, block_hash, parent_hash, timestamp, tx_count, miner, difficulty, gas_used, gas_limit, size, nonce, int(time.time())))
        
        # Индексируем транзакции
        for tx in block.get("transactions", []):
            tx_hash = tx.get("hash", "")
            from_addr = tx.get("from", "")
            to_addr = tx.get("to", "")
            value = tx.get("value", "0x0")
            gas = int(tx.get("gas", "0x0"), 16)
            gas_price = tx.get("gasPrice", "0x0")
            nonce = int(tx.get("nonce", "0x0"), 16)
            tx_input = tx.get("input", "")
            
            cursor.execute('''
                INSERT OR REPLACE INTO transactions 
                (hash, block_number, from_addr, to_addr, value, gas, gas_price, nonce, input, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (tx_hash, height, from_addr, to_addr, value, gas, gas_price, nonce, tx_input, timestamp))
            
            # Обновляем аккаунты
            value_int = int(value, 16) if value else 0
            
            for addr in [from_addr, to_addr]:
                if addr and addr != "0x":
                    cursor.execute("SELECT balance, tx_count FROM accounts WHERE address = ?", (addr,))
                    row = cursor.fetchone()
                    if row:
                        balance = int(row[0], 16) if row[0].startswith("0x") else int(row[0])
                        if addr == from_addr:
                            balance -= value_int
                        else:
                            balance += value_int
                        cursor.execute("UPDATE accounts SET balance = ?, tx_count = ? WHERE address = ?", 
                                     (hex(balance), row[1] + 1, addr))
                    else:
                        balance = -value_int if addr == from_addr else value_int
                        cursor.execute("INSERT INTO accounts (address, balance, tx_count, first_seen, last_seen) VALUES (?, ?, ?, ?, ?)",
                                     (addr, hex(balance) if balance >= 0 else hex(0), 1, timestamp, timestamp))
        
        conn.commit()
        conn.close()
        print(f"   ✅ Block {height}: {tx_count} txs, miner: {miner[:20] if miner else 'unknown'}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error indexing block {height}: {e}")
        return False

def run_indexer():
    """Основной цикл индексатора"""
    print("=" * 50)
    print("🚀 MAINNET INDEXER STARTED")
    print("=" * 50)
    
    # Удаляем старую БД, если есть (чистый старт)
    if os.path.exists(DB_PATH):
        print("📁 Removing old database for clean start...")
        os.remove(DB_PATH)
    
    init_db()
    
    last_indexed = 0
    
    while True:
        try:
            # Получаем текущую высоту
            height_hex = safe_rpc_call("eth_blockNumber", [])
            if not height_hex:
                time.sleep(5)
                continue
            
            current_height = int(height_hex, 16)
            
            # Индексируем новые блоки
            if current_height > last_indexed:
                for h in range(last_indexed + 1, current_height + 1):
                    index_block(h)
                last_indexed = current_height
                print(f"📊 Progress: indexed {last_indexed} blocks")
            
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("\n🛑 Indexer stopped")
            break
        except Exception as e:
            print(f"❌ Indexer error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_indexer()
