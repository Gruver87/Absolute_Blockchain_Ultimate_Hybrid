#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adaptive Indexer - подстраивается под формат ноды"""

import json
import time
import sqlite3
import urllib.request
import urllib.error
import os
import sys

if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocks (
            number INTEGER PRIMARY KEY,
            hash TEXT,
            parent_hash TEXT,
            timestamp INTEGER,
            tx_count INTEGER,
            miner TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            hash TEXT PRIMARY KEY,
            block_number INTEGER,
            from_addr TEXT,
            to_addr TEXT,
            value TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            address TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            tx_count INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def rpc_call(method, params):
    for attempt in range(3):
        try:
            data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode()).get("result")
        except:
            time.sleep(0.5)
    return None

def parse_block(block_data):
    """Гибкий парсинг блока - подстраивается под формат"""
    if not block_data:
        return None
    
    # Если пришла строка - пробуем распарсить JSON
    if isinstance(block_data, str):
        try:
            block_data = json.loads(block_data)
        except:
            return None
    
    if not isinstance(block_data, dict):
        return None
    
    # Извлекаем номер блока
    number = None
    if 'number' in block_data:
        num = block_data['number']
        if isinstance(num, str) and num.startswith('0x'):
            number = int(num, 16)
        else:
            number = int(num) if num is not None else None
    elif 'height' in block_data:
        number = int(block_data['height'])
    
    if number is None:
        return None
    
    # Извлекаем хэш
    block_hash = block_data.get('hash', block_data.get('block_hash', ''))
    
    # Извлекаем parent hash
    parent_hash = block_data.get('parentHash', block_data.get('previous_hash', ''))
    
    # Извлекаем timestamp
    ts = block_data.get('timestamp', 0)
    if isinstance(ts, str) and ts.startswith('0x'):
        timestamp = int(ts, 16)
    else:
        timestamp = int(ts) if ts else 0
    
    # Извлекаем miner
    miner = block_data.get('miner', block_data.get('validator', ''))
    
    # Извлекаем транзакции
    txs = block_data.get('transactions', [])
    tx_count = len(txs) if isinstance(txs, list) else 0
    
    return {
        'number': number,
        'hash': block_hash,
        'parent_hash': parent_hash,
        'timestamp': timestamp,
        'tx_count': tx_count,
        'miner': miner,
        'transactions': txs
    }

def index_block(block_info):
    """Индексация блока"""
    conn = get_conn()
    cursor = conn.cursor()
    
    # Сохраняем блок
    cursor.execute('''
        INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, tx_count, miner)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (block_info['number'], block_info['hash'], block_info['parent_hash'], 
          block_info['timestamp'], block_info['tx_count'], block_info['miner']))
    
    # Сохраняем транзакции
    for tx in block_info['transactions']:
        if isinstance(tx, dict):
            tx_hash = tx.get('hash', '')
            from_addr = tx.get('from', '')
            to_addr = tx.get('to', '')
            value = tx.get('value', '0x0')
            
            cursor.execute('''
                INSERT OR REPLACE INTO transactions (hash, block_number, from_addr, to_addr, value)
                VALUES (?, ?, ?, ?, ?)
            ''', (tx_hash, block_info['number'], from_addr, to_addr, value))
            
            # Обновляем аккаунты (просто счётчик)
            for addr in [from_addr, to_addr]:
                if addr and addr != "0x":
                    cursor.execute("SELECT tx_count FROM accounts WHERE address = ?", (addr,))
                    row = cursor.fetchone()
                    if row:
                        cursor.execute("UPDATE accounts SET tx_count = tx_count + 1 WHERE address = ?", (addr,))
                    else:
                        cursor.execute("INSERT INTO accounts (address, balance, tx_count) VALUES (?, 0, 1)", (addr,))
    
    conn.commit()
    conn.close()
    print(f"   ✅ Block {block_info['number']}: {block_info['tx_count']} txs")

def run():
    print("=" * 50)
    print("🚀 ADAPTIVE INDEXER STARTED")
    print("=" * 50)
    
    init_db()
    
    # Получаем высоту
    height_hex = rpc_call("eth_blockNumber", [])
    if not height_hex:
        print("❌ Cannot get current height")
        return
    
    current = int(height_hex, 16)
    print(f"📊 Current chain height: {current}")
    
    # Проверяем формат блока #1
    print("🔍 Testing block #1 format...")
    test_block = rpc_call("eth_getBlockByNumber", ["0x1", True])
    parsed = parse_block(test_block)
    if parsed:
        print(f"   ✅ Block #1 found! Number: {parsed['number']}")
    else:
        print(f"   ⚠️ Block #1 not found or invalid format")
        print(f"   Raw response: {str(test_block)[:200]}")
    
    # Индексируем все блоки (с #0 или #1)
    print("\n📦 Starting indexing...")
    
    for height in range(1, current + 1):
        hex_h = hex(height)
        block_data = rpc_call("eth_getBlockByNumber", [hex_h, True])
        parsed = parse_block(block_data)
        
        if parsed:
            index_block(parsed)
        else:
            print(f"   ⚠️ Block {height} skipped (invalid format)")
        
        time.sleep(0.1)
    
    print("\n✅ Indexing complete!")
    print(f"📊 Indexed blocks: {current}")

if __name__ == "__main__":
    run()
