#!/usr/bin/env python3
"""LEVEL 11 INDEXER - Event-driven с WebSocket"""

import json
import sqlite3
import urllib.request
import time
import threading
import asyncio
import websockets
from queue import Queue

RPC_URL = "http://localhost:8545"
DB_PATH = "blockchain.db"
WS_PORT = 8765

# Очередь для WebSocket
ws_queue = Queue()

# Состояние в памяти
state = {
    "latest_block": 0,
    "pending_txs": [],
    "blocks": {}
}

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
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

def broadcast(event_type, data):
    """Отправка события в WebSocket"""
    ws_queue.put({"type": event_type, "data": data, "timestamp": int(time.time())})

def save_block(block_data, height):
    """Сохранение блока в БД"""
    conn = get_conn()
    c = conn.cursor()
    
    timestamp = int(block_data.get("timestamp", "0x0"), 16)
    miner = block_data.get("miner", "")
    transactions = block_data.get("transactions", [])
    
    c.execute('''
        INSERT OR REPLACE INTO blocks (number, hash, parent_hash, timestamp, miner, tx_count)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (height, block_data.get("hash", ""), block_data.get("parentHash", ""),
          timestamp, miner, len(transactions)))
    
    for tx in transactions:
        tx_hash = tx.get("hash", "")
        from_addr = tx.get("from", "")
        to_addr = tx.get("to", "")
        value = tx.get("value", "0x0")
        
        c.execute('''
            INSERT OR REPLACE INTO transactions
            (hash, block_number, from_addr, to_addr, value, gas_price, gas_used, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tx_hash, height, from_addr, to_addr, value, "0x1", 21000, 1, timestamp))
        
        for addr in [from_addr, to_addr]:
            if addr and addr != "0x":
                c.execute('''
                    INSERT OR IGNORE INTO addresses (address, balance, tx_count, first_seen, last_seen)
                    VALUES (?, 0, 0, ?, ?)
                ''', (addr, timestamp, timestamp))
                c.execute('''
                    UPDATE addresses SET tx_count = tx_count + 1, last_seen = ?
                    WHERE address = ?
                ''', (timestamp, addr))
    
    conn.commit()
    conn.close()
    
    # Обновляем состояние в памяти
    state["latest_block"] = height
    state["blocks"][height] = {
        "number": height,
        "hash": block_data.get("hash", ""),
        "tx_count": len(transactions),
        "timestamp": timestamp
    }
    
    # Отправляем событие через WebSocket
    broadcast("NEW_BLOCK", {
        "number": height,
        "hash": block_data.get("hash", "")[:16],
        "tx_count": len(transactions),
        "timestamp": timestamp
    })

def indexer_loop():
    """Основной цикл индексатора"""
    last_indexed = 0
    
    while True:
        try:
            node_height = get_node_height()
            
            if node_height > last_indexed:
                for h in range(last_indexed + 1, node_height + 1):
                    print(f"📦 Indexing block {h}...")
                    block_data = rpc_call("eth_getBlockByNumber", [hex(h), True])
                    if block_data and isinstance(block_data, dict):
                        save_block(block_data, h)
                        print(f"   ✅ Block {h} indexed")
                    else:
                        print(f"   ⚠️ Block {h} not found")
                last_indexed = node_height
            
            time.sleep(1)
        except Exception as e:
            print(f"❌ Indexer error: {e}")
            time.sleep(2)

async def websocket_server(websocket, path):
    """WebSocket сервер для real-time обновлений"""
    print(f"🔌 Client connected")
    try:
        while True:
            # Отправляем текущее состояние при подключении
            await websocket.send(json.dumps({
                "type": "STATE",
                "data": {
                    "latest_block": state["latest_block"],
                    "pending_txs": len(state["pending_txs"])
                }
            }))
            
            # Ждём сообщения от клиента (или пульс)
            await asyncio.wait_for(websocket.recv(), timeout=30)
    except:
        print(f"🔌 Client disconnected")

async def ws_broadcaster():
    """Трансляция событий из очереди"""
    while True:
        if not ws_queue.empty():
            event = ws_queue.get()
            # Здесь можно отправлять всем подключённым клиентам
            print(f"📡 Event: {event['type']}")
        await asyncio.sleep(0.1)

def run_websocket():
    """Запуск WebSocket сервера"""
    asyncio.run(start_ws())

async def start_ws():
    async with websockets.serve(websocket_server, "localhost", WS_PORT):
        print(f"🌐 WebSocket server running on ws://localhost:{WS_PORT}")
        await asyncio.Future()  # run forever

def main():
    print("=" * 60)
    print("🚀 LEVEL 11 INDEXER (Event-driven + WebSocket)")
    print("=" * 60)
    
    # Запускаем индексатор в отдельном потоке
    indexer_thread = threading.Thread(target=indexer_loop, daemon=True)
    indexer_thread.start()
    
    # Запускаем WebSocket сервер
    try:
        asyncio.run(start_ws())
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")

if __name__ == "__main__":
    main()
