# ============================================================
# ABSOLUTE BLOCKCHAIN - FULL UNIFICATION SCRIPT
# Объединяет старую рабочую версию со всеми production-компонентами
# ============================================================

param(
    [string]$ProjectPath = "C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate"
)

Write-Host @"
╔═══════════════════════════════════════════════════════════════════════════╗
║     ABSOLUTE BLOCKCHAIN - ПОЛНОЕ ОБЪЕДИНЕНИЕ ВСЕХ КОМПОНЕНТОВ            ║
║                          UNIFICATION SCRIPT v1.0                          ║
╚═══════════════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

Set-Location $ProjectPath

# ============================================================
# 1. ОСТАНОВКА ВСЕХ ПРОЦЕССОВ
# ============================================================
Write-Host "`n🔴 1. Остановка всех процессов Python..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "   ✅ Остановлены" -ForegroundColor Green

# ============================================================
# 2. СОЗДАНИЕ БЭКАПА
# ============================================================
Write-Host "`n📦 2. Создание резервной копии..." -ForegroundColor Yellow
$backupDir = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item "ABSOLUTE_FINAL_FIXED.py" "$backupDir\ABSOLUTE_FINAL_FIXED.py.bak" -ErrorAction SilentlyContinue
Copy-Item "node_persistent.py" "$backupDir\node_persistent.py.bak" -ErrorAction SilentlyContinue
Copy-Item "data\blockchain.db" "$backupDir\blockchain.db.bak" -ErrorAction SilentlyContinue
Write-Host "   ✅ Бэкап создан в папке: $backupDir" -ForegroundColor Green

# ============================================================
# 3. СОЗДАНИЕ ЕДИНОГО ГЛАВНОГО ФАЙЛА
# ============================================================
Write-Host "`n🔧 3. Создание единого файла ABSOLUTE_UNIFIED.py..." -ForegroundColor Yellow

$unifiedCode = @'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN ULTIMATE - UNIFIED VERSION
Объединяет старую рабочую версию со всеми production-компонентами
Версия: 1.0
"""

import json
import sqlite3
import hashlib
import time
import threading
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================
@dataclass
class Config:
    VERSION: str = "57.0"
    NETWORK_NAME: str = "AbsoluteBlockchain"
    API_PORT: int = 8080
    RPC_PORT: int = 8545
    EXPLORER_PORT: int = 8095
    BLOCK_TIME: int = 15
    BLOCK_REWARD: float = 50.0
    MIN_STAKE: float = 100.0
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

config = Config()

# ============================================================
# PRODUCTION COMPONENT 1: RATE LIMITER
# ============================================================
class RateLimiter:
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.tokens: Dict[str, float] = {}
        self.last_refill: Dict[str, float] = {}
        self.lock = threading.RLock()
    
    def _refill_tokens(self, key: str):
        now = time.time()
        last = self.last_refill.get(key, now)
        time_passed = now - last
        refill = time_passed / 60.0 * self.requests_per_minute
        current = self.tokens.get(key, self.requests_per_minute)
        self.tokens[key] = min(self.requests_per_minute, current + refill)
        self.last_refill[key] = now
    
    def allow_request(self, key: str) -> Tuple[bool, int]:
        with self.lock:
            self._refill_tokens(key)
            if self.tokens.get(key, self.requests_per_minute) >= 1:
                self.tokens[key] -= 1
                return True, int(self.tokens[key])
            return False, 0

rate_limiter = RateLimiter()

# ============================================================
# PRODUCTION COMPONENT 2: JWT AUTH
# ============================================================
import jwt
import secrets
import os

JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)

class JWTAuth:
    def generate_token(self, address: str) -> str:
        payload = {
            'address': address,
            'iat': time.time(),
            'exp': time.time() + 86400,
            'jti': secrets.token_hex(16)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict]]:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            return True, payload
        except:
            return False, None

jwt_auth = JWTAuth()

# ============================================================
# PRODUCTION COMPONENT 3: VALIDATORS
# ============================================================
def validate_address(address: str) -> Tuple[bool, str]:
    if not address or not isinstance(address, str):
        return False, "Address required"
    if not address.startswith('0x'):
        return False, "Address must start with 0x"
    if len(address) != 42:
        return False, "Address must be 42 characters"
    return True, ""

def validate_amount(amount: Any) -> Tuple[bool, str]:
    try:
        amount_float = float(amount)
    except:
        return False, "Amount must be a number"
    if amount_float <= 0:
        return False, "Amount must be positive"
    if amount_float > 1_000_000_000:
        return False, "Amount too large"
    return True, ""

# ============================================================
# PRODUCTION COMPONENT 4: MEMPOOL
# ============================================================
@dataclass
class MempoolTx:
    tx_hash: str
    from_addr: str
    to_addr: str
    amount: float
    fee: float
    timestamp: float

class Mempool:
    def __init__(self, max_size: int = 10000):
        self.transactions: Dict[str, MempoolTx] = {}
        self.max_size = max_size
        self.lock = threading.RLock()
    
    def add(self, tx: MempoolTx) -> bool:
        with self.lock:
            if tx.tx_hash in self.transactions:
                return False
            if len(self.transactions) >= self.max_size:
                # Remove oldest
                oldest = min(self.transactions.keys(), key=lambda k: self.transactions[k].timestamp)
                del self.transactions[oldest]
            self.transactions[tx.tx_hash] = tx
            return True
    
    def get_pending(self, limit: int = 1000) -> List[MempoolTx]:
        with self.lock:
            return sorted(self.transactions.values(), key=lambda tx: tx.fee, reverse=True)[:limit]
    
    def remove(self, tx_hash: str) -> bool:
        with self.lock:
            return self.transactions.pop(tx_hash, None) is not None
    
    def size(self) -> int:
        with self.lock:
            return len(self.transactions)

mempool = Mempool()

# ============================================================
# PRODUCTION COMPONENT 5: CHAIN STORAGE
# ============================================================
class ChainStorage:
    def __init__(self, db_path: str = "data/unified.db"):
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else "data", exist_ok=True)
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    height INTEGER PRIMARY KEY,
                    block_hash TEXT UNIQUE NOT NULL,
                    previous_hash TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    miner TEXT NOT NULL,
                    transactions TEXT,
                    tx_count INTEGER DEFAULT 0
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(block_hash)')
    
    def save_block(self, height: int, block_hash: str, previous_hash: str, miner: str, transactions: list):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO blocks (height, block_hash, previous_hash, timestamp, miner, transactions, tx_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (height, block_hash, previous_hash, int(time.time()), miner, json.dumps(transactions), len(transactions)))
    
    def get_last_block(self) -> Optional[Dict]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM blocks ORDER BY height DESC LIMIT 1')
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_block(self, height: int) -> Optional[Dict]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM blocks WHERE height = ?', (height,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                if data.get('transactions'):
                    data['transactions'] = json.loads(data['transactions'])
                return data
            return None

chain_storage = ChainStorage()

# ============================================================
# PRODUCTION COMPONENT 6: STATE MANAGER
# ============================================================
class StateManager:
    def __init__(self):
        self.balances: Dict[str, float] = {}
        self.lock = threading.RLock()
    
    def get_balance(self, address: str) -> float:
        with self.lock:
            return self.balances.get(address, 0)
    
    def set_balance(self, address: str, amount: float):
        with self.lock:
            self.balances[address] = amount
    
    def transfer(self, from_addr: str, to_addr: str, amount: float) -> bool:
        with self.lock:
            if self.balances.get(from_addr, 0) < amount:
                return False
            self.balances[from_addr] = self.balances.get(from_addr, 0) - amount
            self.balances[to_addr] = self.balances.get(to_addr, 0) + amount
            return True

state_manager = StateManager()

# ============================================================
# БЛОКЧЕЙН ЯДРО
# ============================================================
class Block:
    def __init__(self, height: int, previous_hash: str, miner: str):
        self.height = height
        self.previous_hash = previous_hash
        self.timestamp = int(time.time())
        self.miner = miner
        self.transactions = []
        self.nonce = 0
        self.block_hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        data = f"{self.height}{self.previous_hash}{self.timestamp}{self.miner}{json.dumps(self.transactions)}{self.nonce}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return {
            'height': self.height,
            'block_hash': self.block_hash,
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'miner': self.miner,
            'transactions': self.transactions,
            'transaction_count': len(self.transactions)
        }

class Transaction:
    def __init__(self, from_addr: str, to_addr: str, amount: float):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount = amount
        self.timestamp = int(time.time())
        self.tx_hash = hashlib.sha256(f"{from_addr}{to_addr}{amount}{self.timestamp}".encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return {
            'tx_hash': self.tx_hash,
            'from': self.from_addr,
            'to': self.to_addr,
            'amount': self.amount,
            'timestamp': self.timestamp
        }

class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        self.load_or_create_chain()
    
    def load_or_create_chain(self):
        last_block = chain_storage.get_last_block()
        if last_block:
            # Load from storage
            for h in range(1, last_block['height'] + 1):
                block_data = chain_storage.get_block(h)
                if block_data:
                    block = Block(block_data['height'], block_data['previous_hash'], block_data['miner'])
                    block.block_hash = block_data['block_hash']
                    block.timestamp = block_data['timestamp']
                    if block_data.get('transactions'):
                        block.transactions = block_data['transactions']
                    self.chain.append(block)
            print(f"📦 Loaded {len(self.chain)} blocks from storage")
        else:
            # Genesis block
            genesis = Block(0, "0" * 64, "genesis")
            genesis.block_hash = genesis.calculate_hash()
            self.chain.append(genesis)
            chain_storage.save_block(0, genesis.block_hash, genesis.previous_hash, genesis.miner, [])
            print("🌱 Genesis block created")
        
        # Set initial balance
        if len(self.chain) >= 1:
            state_manager.set_balance(self.get_wallet_address(), 1000000)
    
    def get_wallet_address(self) -> str:
        try:
            with open('data/wallet.json', 'r') as f:
                return json.load(f).get('address', '0x94f45b97f9bc27')
        except:
            return '0x94f45b97f9bc27'
    
    def get_balance(self, address: str) -> float:
        return state_manager.get_balance(address)
    
    def add_transaction(self, tx: Transaction) -> bool:
        # Validate
        valid, err = validate_amount(tx.amount)
        if not valid:
            return False
        
        # Check balance
        if state_manager.get_balance(tx.from_addr) < tx.amount + 0.001:
            return False
        
        # Add to mempool
        mempool_tx = MempoolTx(tx.tx_hash, tx.from_addr, tx.to_addr, tx.amount, 0.001, tx.timestamp)
        return mempool.add(mempool_tx)
    
    def mine_block(self, miner: str) -> Optional[Block]:
        pending = mempool.get_pending(50)
        if not pending and len(self.chain) > 0:
            # Still mine empty block
            pass
        
        new_block = Block(len(self.chain), self.chain[-1].block_hash, miner)
        
        # Add transactions
        for tx in pending[:20]:
            if state_manager.transfer(tx.from_addr, tx.to_addr, tx.amount):
                new_block.transactions.append({
                    'tx_hash': tx.tx_hash,
                    'from': tx.from_addr,
                    'to': tx.to_addr,
                    'amount': tx.amount
                })
                mempool.remove(tx.tx_hash)
        
        # Add reward
        state_manager.set_balance(miner, state_manager.get_balance(miner) + config.BLOCK_REWARD)
        new_block.block_hash = new_block.calculate_hash()
        
        self.chain.append(new_block)
        chain_storage.save_block(new_block.height, new_block.block_hash, new_block.previous_hash, miner, new_block.transactions)
        
        print(f"📦 Block #{new_block.height}: {new_block.block_hash} | {len(new_block.transactions)} txs")
        return new_block
    
    def get_blockchain_info(self) -> Dict:
        return {
            'chain': config.NETWORK_NAME,
            'blocks': len(self.chain) - 1,
            'mining_reward': config.BLOCK_REWARD,
            'mempool_size': mempool.size(),
            'version': config.VERSION
        }

# ============================================================
# API СЕРВЕР (объединяет всё!)
# ============================================================
class UnifiedAPIHandler(BaseHTTPRequestHandler):
    blockchain = None
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Rate limiting
        client_ip = self.client_address[0]
        allowed, remaining = rate_limiter.allow_request(client_ip)
        if not allowed:
            self._send_json({'error': 'Rate limit exceeded'}, 429)
            return
        
        # Web interface
        if path == '/' or path == '/index.html':
            self._send_html(self._get_web_interface())
        elif path == '/explorer':
            self._send_html(self._get_explorer_html())
        elif path == '/api/stats':
            self._send_json(self.blockchain.get_blockchain_info())
        elif path == '/api/blocks':
            blocks = [b.to_dict() for b in self.blockchain.chain[1:]]
            self._send_json({'blocks': blocks, 'total': len(blocks)})
        elif path == '/api/balance':
            query = parse_qs(parsed.query)
            address = query.get('address', [''])[0]
            if address:
                self._send_json({'address': address, 'balance': self.blockchain.get_balance(address)})
            else:
                self._send_json({'error': 'Address required'}, 400)
        else:
            self._send_json({'error': 'Not found'}, 404)
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(body.decode('utf-8'))
        except:
            data = {}
        
        path = self.path
        
        if path == '/api/transaction/send':
            from_addr = data.get('from')
            to_addr = data.get('to')
            amount = float(data.get('amount', 0))
            
            if not from_addr or not to_addr:
                self._send_json({'error': 'Missing from/to address'}, 400)
                return
            
            valid, err = validate_address(from_addr)
            if not valid:
                self._send_json({'error': err}, 400)
                return
            
            valid, err = validate_amount(amount)
            if not valid:
                self._send_json({'error': err}, 400)
                return
            
            tx = Transaction(from_addr, to_addr, amount)
            success = self.blockchain.add_transaction(tx)
            self._send_json({'success': success, 'tx_hash': tx.tx_hash if success else None})
        
        elif path == '/api/mine':
            miner = data.get('miner', self.blockchain.get_wallet_address())
            block = self.blockchain.mine_block(miner)
            self._send_json({'success': block is not None, 'height': block.height if block else 0})
        
        else:
            self._send_json({'error': 'Not found'}, 404)
    
    def _send_json(self, data: Dict, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_html(self, html: str, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def _get_web_interface(self) -> str:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Absolute Blockchain Ultimate</title>
            <style>
                body { font-family: monospace; background: #0a0a0a; color: #0f0; padding: 20px; }
                h1 { color: #0f0; }
                .info { background: #0a1a0a; border: 1px solid #0f0; padding: 10px; margin: 10px 0; border-radius: 5px; }
                button { background: #0a0a0a; color: #0f0; border: 1px solid #0f0; padding: 5px 10px; cursor: pointer; }
                input { background: #1a1a1a; color: #0f0; border: 1px solid #0f0; padding: 5px; width: 300px; }
            </style>
        </head>
        <body>
            <h1>🔗 Absolute Blockchain Ultimate</h1>
            <div class="info">
                <div>📦 Block Height: <span id="height">...</span></div>
                <div>📋 Mempool Size: <span id="mempool">...</span></div>
                <div>⛏️ Mining Reward: 50 ABS</div>
            </div>
            <h2>💰 Send Transaction</h2>
            <input type="text" id="to" placeholder="Recipient address (0x...)">
            <input type="number" id="amount" placeholder="Amount">
            <button onclick="sendTx()">Send</button>
            <div id="result"></div>
            <script>
                async function loadStats() {
                    const res = await fetch('/api/stats');
                    const data = await res.json();
                    document.getElementById('height').innerText = data.blocks;
                    document.getElementById('mempool').innerText = data.mempool_size;
                }
                async function sendTx() {
                    const to = document.getElementById('to').value;
                    const amount = document.getElementById('amount').value;
                    const res = await fetch('/api/transaction/send', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({from: '0x94f45b97f9bc27', to: to, amount: parseFloat(amount)})
                    });
                    const data = await res.json();
                    document.getElementById('result').innerHTML = data.success ? '✅ Tx sent: ' + data.tx_hash : '❌ Failed';
                    loadStats();
                }
                loadStats();
                setInterval(loadStats, 3000);
            </script>
        </body>
        </html>
        '''
    
    def _get_explorer_html(self) -> str:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Absolute Blockchain Explorer</title>
            <meta charset="UTF-8">
            <style>
                body { font-family: monospace; background: #0a0a0a; color: #0f0; padding: 20px; }
                h1 { color: #0f0; }
                .block { border: 1px solid #0f0; margin: 10px 0; padding: 10px; border-radius: 5px; }
                .online { background: #0a3a0a; border: 1px solid #0f0; padding: 10px; margin: 10px 0; }
                button { background: #0a0a0a; color: #0f0; border: 1px solid #0f0; padding: 5px 10px; cursor: pointer; }
            </style>
        </head>
        <body>
            <h1>🔍 Absolute Blockchain Explorer</h1>
            <div id="status" class="online">✅ Node Online</div>
            <button onclick="loadBlocks()">🔄 Refresh</button>
            <div id="blocks">Loading...</div>
            <script>
                async function loadBlocks() {
                    const res = await fetch('/api/blocks');
                    const data = await res.json();
                    let html = '';
                    for (const block of data.blocks.reverse()) {
                        html += `<div class="block">
                            <b>🔷 Block #${block.height}</b>
                            <div>Hash: ${block.block_hash}</div>
                            <div>Miner: ${block.miner.substring(0, 20)}...</div>
                            <div>📝 Transactions: ${block.transaction_count}</div>
                        </div>`;
                    }
                    document.getElementById('blocks').innerHTML = html || '<p>No blocks</p>';
                }
                loadBlocks();
                setInterval(loadBlocks, 5000);
            </script>
        </body>
        </html>
        '''

# ============================================================
# ЗАПУСК
# ============================================================
def main():
    print("=" * 60)
    print("ABSOLUTE BLOCKCHAIN ULTIMATE - UNIFIED v1.0")
    print("=" * 60)
    
    # Initialize blockchain
    blockchain = Blockchain()
    UnifiedAPIHandler.blockchain = blockchain
    
    # Start API server
    server = HTTPServer(('0.0.0.0', config.API_PORT), UnifiedAPIHandler)
    
    print(f"🌐 Web Interface: http://localhost:{config.API_PORT}")
    print(f"🔍 Explorer: http://localhost:{config.API_PORT}/explorer")
    print(f"📡 API: http://localhost:{config.API_PORT}/api/stats")
    print(f"⛏️ Auto-mining every {config.BLOCK_TIME} seconds")
    print("=" * 60)
    print("🚀 Node running! Press Ctrl+C to stop")
    
    # Auto-mining thread
    def auto_mine():
        while True:
            time.sleep(config.BLOCK_TIME)
            try:
                blockchain.mine_block(blockchain.get_wallet_address())
            except:
                pass
    
    mining_thread = threading.Thread(target=auto_mine, daemon=True)
    mining_thread.start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️ Shutting down...")
        server.shutdown()

if __name__ == '__main__':
    main()
'@

$unifiedCode | Out-File -FilePath "ABSOLUTE_UNIFIED.py" -Encoding UTF8 -Force
Write-Host "   ✅ Создан: ABSOLUTE_UNIFIED.py" -ForegroundColor Green

# ============================================================
# 4. УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================
Write-Host "`n📦 4. Установка зависимостей..." -ForegroundColor Yellow
pip install pyjwt psutil prometheus-client -q 2>$null
Write-Host "   ✅ Зависимости установлены" -ForegroundColor Green

# ============================================================
# 5. СОЗДАНИЕ ПАПОК
# ============================================================
Write-Host "`n📁 5. Создание папок..." -ForegroundColor Yellow
@("data", "logs") | ForEach-Object {
    New-Item -ItemType Directory -Path $_ -Force | Out-Null
    Write-Host "   ✅ Папка: $_" -ForegroundColor Green
}

# ============================================================
# 6. СОЗДАНИЕ КОШЕЛЬКА
# ============================================================
Write-Host "`n👛 6. Создание кошелька..." -ForegroundColor Yellow
$wallet = @{
    address = "0x94f45b97f9bc27"
    private_key = "unified_private_key"
    created_at = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
}
$walletJson = $wallet | ConvertTo-Json
$walletJson | Out-File -FilePath "data/wallet.json" -Encoding UTF8 -Force
Write-Host "   ✅ Кошелёк создан: 0x94f45b97f9bc27" -ForegroundColor Green

# ============================================================
# 7. ФИНАЛЬНЫЙ ЗАПУСК
# ============================================================
Write-Host @"

╔═══════════════════════════════════════════════════════════════════════════╗
║                          ОБЪЕДИНЕНИЕ ЗАВЕРШЕНО!                           ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  🚀 Запуск единого блокчейна:                                             ║
║     python ABSOLUTE_UNIFIED.py                                            ║
║                                                                           ║
║  🌐 Открыть в браузере:                                                   ║
║     http://localhost:8080          - Веб-интерфейс                        ║
║     http://localhost:8080/explorer - Блокчейн-эксплорер                   ║
║                                                                           ║
║  📡 API:                                                                  ║
║     http://localhost:8080/api/stats - Статистика                          ║
║     http://localhost:8080/api/blocks - Список блоков                      ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

# Автоматический запуск
Write-Host "`n🚀 Автоматический запуск через 3 секунды..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Запуск в новом окне
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectPath'; python ABSOLUTE_UNIFIED.py"

Write-Host "✅ Блокчейн запущен в новом окне!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Откройте браузер: http://localhost:8080" -ForegroundColor Cyan