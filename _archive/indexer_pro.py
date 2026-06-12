# indexer_pro.py - PRO индексатор для Etherscan
import json
import time
import urllib.request
import urllib.error
from db import get_conn, init_db

RPC_URL = "http://localhost:8545"

# Инициализируем БД
init_db()

def safe_rpc_call(method, params, retries=3):
    """Безопасный RPC вызов с retry"""
    for attempt in range(retries):
        try:
            data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode())["result"]
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.5)
            else:
                print(f"RPC failed after {retries} attempts: {method}")
                return None
    return None

def update_account_balance(address, delta):
    """Обновление баланса аккаунта"""
    if not address or address == "0x":
        return
    
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance, tx_count FROM accounts WHERE address = ?", (address,))
    row = cursor.fetchone()
    
    if row:
        balance = row[0] + delta
        tx_count = row[1] + 1
        cursor.execute("UPDATE accounts SET balance = ?, tx_count = ? WHERE address = ?", (balance, tx_count, address))
    else:
        cursor.execute("INSERT INTO accounts (address, balance, tx_count) VALUES (?, ?, ?)", (address, delta, 1))
    
    conn.commit()
    conn.close()

def index_block(height):
    """Индексация одного блока"""
    print(f"📦 Indexing block {height}...")
    
    # Получаем блок
    block = safe_rpc_call("eth_getBlockByNumber", [hex(height), True])
    if not block:
        print(f"   ⚠️ Block {height} not found")
        return
    
    # Извлекаем данные
    block_hash = block.get("hash", "")
    timestamp = int(block.get("timestamp", "0x0"), 16)
    tx_count = len(block.get("transactions", []))
    miner = block.get("miner", "")
    
    # Сохраняем блок
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO blocks (number, hash, timestamp, tx_count, miner)
        VALUES (?, ?, ?, ?, ?)
    ''', (height, block_hash, timestamp, tx_count, miner))
    conn.commit()
    
    # Индексируем транзакции
    for tx in block.get("transactions", []):
        tx_hash = tx.get("hash", "")
        from_addr = tx.get("from", "")
        to_addr = tx.get("to", "")
        value = tx.get("value", "0x0")
        
        # Сохраняем транзакцию
        cursor.execute('''
            INSERT OR REPLACE INTO transactions (hash, block_number, from_addr, to_addr, value, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (tx_hash, height, from_addr, to_addr, value, timestamp))
        
        # Обновляем балансы (упрощённо)
        value_int = int(value, 16) if value else 0
        if from_addr and from_addr != "0x":
            update_account_balance(from_addr, -value_int)
        if to_addr and to_addr != "0x":
            update_account_balance(to_addr, value_int)
    
    conn.commit()
    conn.close()
    print(f"   ✅ Block {height}: {tx_count} txs, miner: {miner[:20]}...")

def run_indexer():
    """Основной цикл индексатора"""
    print("=" * 50)
    print("🚀 ETHERSCAN PRO INDEXER STARTED")
    print("=" * 50)
    
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
            for h in range(last_indexed + 1, current_height + 1):
                index_block(h)
            
            last_indexed = current_height
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("\n🛑 Indexer stopped")
            break
        except Exception as e:
            print(f"❌ Indexer error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_indexer()
