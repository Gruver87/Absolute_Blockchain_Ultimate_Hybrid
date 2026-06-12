#!/usr/bin/env python3
"""ABSOLUTE BLOCKCHAIN - УНИВЕРСАЛЬНЫЙ СЕРВЕР v54"""

import json
import sqlite3
import hashlib
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================
VERSION = "54.0"
RPC_PORT = 8545
WEB_PORT = 8080
BLOCK_REWARD = 50.0

# ============================================================
# ДАННЫЕ
# ============================================================
blocks = []
balances = {"0x40e908721295de4a5cbc775abac8909781aeeea8": 29999000}
mempool = []

# ============================================================
# ЗАГРУЗКА ЦЕПОЧКИ
# ============================================================
os.makedirs("data", exist_ok=True)
chain_file = "data/chain.json"

if os.path.exists(chain_file):
    try:
        with open(chain_file, 'r') as f:
            blocks = json.load(f)
        print(f"📦 Loaded chain: {len(blocks)} blocks")
    except:
        blocks = []
else:
    # Генезис блок
    blocks.append({
        "height": 0,
        "block_hash": "0x" + hashlib.sha256(b"genesis").hexdigest()[:14],
        "previous_hash": "0x" + "0" * 64,
        "timestamp": int(time.time()),
        "miner": "genesis",
        "transactions": [],
        "transaction_count": 0
    })
    with open(chain_file, 'w') as f:
        json.dump(blocks, f, indent=2)
    print("🌱 Genesis block created")

# ============================================================
# ФУНКЦИИ БЛОКЧЕЙНА
# ============================================================
def get_block_count():
    return len(blocks) - 1

def get_balance(address):
    return balances.get(address, 0)

def get_wallet_address():
    return "0x40e908721295de4a5cbc775abac8909781aeeea8"

def get_last_blocks(limit=10):
    return blocks[-limit:][::-1]

def send_transaction(from_addr, to_addr, amount):
    if get_balance(from_addr) < amount:
        return False, "Insufficient balance"
    
    tx_hash = hashlib.sha256(f"{from_addr}{to_addr}{amount}{time.time()}".encode()).hexdigest()[:16]
    mempool.append({
        "tx_hash": tx_hash,
        "from": from_addr,
        "to": to_addr,
        "amount": amount,
        "timestamp": int(time.time())
    })
    
    # В реальном блокчейне тут списание, для теста:
    # balances[from_addr] = balances.get(from_addr, 0) - amount
    # balances[to_addr] = balances.get(to_addr, 0) + amount
    
    return True, tx_hash

def mine_block():
    miner = get_wallet_address()
    last_block = blocks[-1]
    
    new_block = {
        "height": len(blocks),
        "block_hash": "0x" + hashlib.sha256(f"{len(blocks)}{last_block['block_hash']}{time.time()}".encode()).hexdigest()[:14],
        "previous_hash": last_block['block_hash'],
        "timestamp": int(time.time()),
        "miner": miner,
        "transactions": mempool.copy(),
        "transaction_count": len(mempool)
    }
    
    # Очищаем мемпул
    mempool.clear()
    
    # Добавляем награду
    balances[miner] = balances.get(miner, 0) + BLOCK_REWARD
    
    blocks.append(new_block)
    
    # Сохраняем
    with open(chain_file, 'w') as f:
        json.dump(blocks, f, indent=2)
    
    print(f"📦 Block #{new_block['height']}: {new_block['block_hash'][:16]} | {new_block['transaction_count']} txs")
    return new_block

# ============================================================
# HTTP СЕРВЕР
# ============================================================
class UnifiedHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/' or path == '/index.html':
            self._send_html(HTML)
        elif path == '/explorer':
            self._send_html(HTML)
        elif path == '/api/stats':
            self._send_json({
                "blocks": get_block_count(),
                "version": VERSION,
                "mempool_size": len(mempool),
                "balance": get_balance(get_wallet_address())
            })
        elif path == '/api/blocks':
            self._send_json({"blocks": get_last_blocks(20), "total": get_block_count()})
        elif path == '/api/balance':
            query = parse_qs(parsed.query)
            address = query.get('address', [''])[0]
            if address:
                self._send_json({"address": address, "balance": get_balance(address)})
            else:
                self._send_json({"error": "Address required"}, 400)
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b'{}'
        
        try:
            data = json.loads(body.decode())
        except:
            data = {}
        
        path = self.path
        
        if path == '/api/transaction/send':
            from_addr = data.get('from', get_wallet_address())
            to_addr = data.get('to')
            amount = float(data.get('amount', 0))
            
            if not to_addr:
                self._send_json({"success": False, "error": "Missing to address"}, 400)
                return
            
            success, result = send_transaction(from_addr, to_addr, amount)
            self._send_json({"success": success, "tx_hash": result if success else None, "error": result if not success else None})
        
        elif path == '/api/mine':
            block = mine_block()
            self._send_json({"success": True, "height": block['height']})
        
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_html(self, html, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

# ============================================================
# HTML СТРАНИЦА
# ============================================================
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Absolute Blockchain Explorer</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: monospace; background: #0a0a0a; color: #0f0; padding: 20px; }
        h1 { color: #0f0; }
        .online { background: #0a3a0a; border: 1px solid #0f0; padding: 10px; margin: 10px 0; border-radius: 5px; }
        .block { border: 1px solid #0f0; margin: 10px 0; padding: 10px; border-radius: 5px; }
        .info { display: inline-block; margin: 5px; padding: 5px 10px; background: #1a1a1a; border-radius: 5px; }
        button { background: #0a0a0a; color: #0f0; border: 1px solid #0f0; padding: 5px 10px; cursor: pointer; }
        input { background: #1a1a1a; color: #0f0; border: 1px solid #0f0; padding: 5px; width: 300px; }
    </style>
</head>
<body>
    <h1>🔗 Absolute Blockchain Explorer</h1>
    <div id="status" class="online">🔄 Loading...</div>
    
    <div class="info">📦 Height: <span id="height">?</span></div>
    <div class="info">👛 Balance: <span id="balance">?</span> ABS</div>
    <div class="info">📋 Mempool: <span id="mempool">?</span></div>
    
    <button onclick="refresh()">🔄 Refresh</button>
    <hr>
    
    <h2>💰 Send Transaction</h2>
    <input type="text" id="toAddr" placeholder="Recipient address (0x...)">
    <input type="number" id="amount" placeholder="Amount (ABS)">
    <button onclick="sendTx()">Send</button>
    <div id="txResult"></div>
    
    <h2>📦 Latest Blocks</h2>
    <button onclick="mineBlock()">⛏️ Mine Block</button>
    <div id="blocks">Loading...</div>
    
    <script>
        const API = 'http://localhost:8080';
        
        async function refresh() {
            try {
                const statsRes = await fetch(API + '/api/stats');
                const stats = await statsRes.json();
                document.getElementById('height').innerText = stats.blocks;
                document.getElementById('balance').innerText = stats.balance;
                document.getElementById('mempool').innerText = stats.mempool_size;
                document.getElementById('status').innerHTML = '✅ Connected to node';
                
                const blocksRes = await fetch(API + '/api/blocks');
                const blocksData = await blocksRes.json();
                let html = '';
                for (const block of blocksData.blocks) {
                    html += `<div class="block">
                        <b>🔷 Block #${block.height}</b>
                        <div>Hash: ${block.block_hash?.substring(0, 30)}...</div>
                        <div>Miner: ${block.miner?.substring(0, 25)}...</div>
                        <div>📝 Transactions: ${block.transaction_count || 0}</div>
                        <div>⏱️ Time: ${new Date(block.timestamp * 1000).toLocaleTimeString()}</div>
                    </div>`;
                }
                document.getElementById('blocks').innerHTML = html || '<p>No blocks</p>';
            } catch(e) {
                document.getElementById('status').innerHTML = '❌ Node offline';
            }
        }
        
        async function sendTx() {
            const to = document.getElementById('toAddr').value;
            const amount = document.getElementById('amount').value;
            if (!to || !amount) {
                document.getElementById('txResult').innerHTML = '❌ Fill all fields';
                return;
            }
            try {
                const res = await fetch(API + '/api/transaction/send', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({to: to, amount: parseFloat(amount)})
                });
                const data = await res.json();
                document.getElementById('txResult').innerHTML = data.success ? '✅ Tx sent: ' + data.tx_hash : '❌ ' + data.error;
                refresh();
            } catch(e) {
                document.getElementById('txResult').innerHTML = '❌ Error';
            }
        }
        
        async function mineBlock() {
            try {
                const res = await fetch(API + '/api/mine', {method: 'POST'});
                const data = await res.json();
                if (data.success) {
                    document.getElementById('txResult').innerHTML = '✅ Block #' + data.height + ' mined!';
                    refresh();
                }
            } catch(e) {
                document.getElementById('txResult').innerHTML = '❌ Mining error';
            }
        }
        
        refresh();
        setInterval(refresh, 3000);
    </script>
</body>
</html>
'''

# ============================================================
# АВТОМАЙНИНГ
# ============================================================
def auto_mine():
    while True:
        time.sleep(15)
        try:
            mine_block()
        except:
            pass

# ============================================================
# ЗАПУСК
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("ABSOLUTE BLOCKCHAIN - UNIFIED SERVER v54")
    print("=" * 60)
    print(f"🌐 Web Interface: http://localhost:{WEB_PORT}")
    print(f"📡 API: http://localhost:{WEB_PORT}/api/stats")
    print(f"🔍 Explorer: http://localhost:{WEB_PORT}/explorer")
    print("=" * 60)
    print("⛏️ Auto-mining every 15 seconds")
    print("🚀 Server running! Press Ctrl+C to stop")
    print("=" * 60)
    
    # Запуск автомайнинга
    mining_thread = threading.Thread(target=auto_mine, daemon=True)
    mining_thread.start()
    
    # Запуск сервера
    server = HTTPServer(('0.0.0.0', WEB_PORT), UnifiedHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️ Shutting down...")
        server.shutdown()
