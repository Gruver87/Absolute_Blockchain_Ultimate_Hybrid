#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RPC Proxy для Blockchain Explorer - Исправленная версия"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error

RPC_URL = "http://localhost:8545"

class ProxyHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = self.path
        
        if path == '/' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif path == '/api/stats':
            self._proxy_to_rpc('eth_blockNumber')
        elif path == '/api/blocks':
            self._get_blocks()
        elif path.startswith('/api/balance'):
            self._get_balance()
        else:
            self._proxy_to_rpc('eth_blockNumber')
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b'{}'
        
        if self.path == '/api/transaction/send':
            self._send_transaction(body)
        elif self.path == '/api/mine':
            self._mine_block(body)
        else:
            self._proxy_rpc_request(body)
    
    def _proxy_rpc_request(self, body):
        """Проксирование RPC запросов"""
        try:
            req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                result = response.read().decode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(result.encode())
        except Exception as e:
            self._send_error(500, str(e))
    
    def _proxy_to_rpc(self, method):
        """Проксирование простого RPC метода"""
        body = json.dumps({"jsonrpc": "2.0", "method": method, "params": [], "id": 1}).encode()
        self._proxy_rpc_request(body)
    
    def _get_blocks(self):
        """Получение списка блоков"""
        # Пробуем получить блоки через RPC
        blocks = []
        try:
            # Получаем текущий блок
            req = urllib.request.Request(RPC_URL, data=json.dumps({"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}).encode(), headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                current = int(data.get('result', '0x0'), 16)
            
            # Получаем последние 10 блоков
            for height in range(max(0, current-9), current+1):
                req = urllib.request.Request(RPC_URL, data=json.dumps({"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":[hex(height), True],"id":1}).encode(), headers={'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        block_data = json.loads(response.read().decode())
                        block = block_data.get('result')
                        if block:
                            blocks.append({
                                "height": int(block.get('number', '0x0'), 16),
                                "block_hash": block.get('hash', ''),
                                "previous_hash": block.get('parentHash', ''),
                                "timestamp": int(block.get('timestamp', '0x0'), 16),
                                "miner": block.get('miner', ''),
                                "transaction_count": len(block.get('transactions', [])),
                                "transactions": block.get('transactions', [])
                            })
                except:
                    pass
        except Exception as e:
            pass
        
        self._send_json({"blocks": blocks, "total": len(blocks)})
    
    def _get_balance(self):
        """Получение баланса"""
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        address = query.get('address', [''])[0]
        
        if address:
            body = json.dumps({"jsonrpc":"2.0","method":"eth_getBalance","params":[address, "latest"],"id":1}).encode()
            try:
                req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    balance = int(data.get('result', '0x0'), 16) / 10**18
                    self._send_json({"address": address, "balance": balance})
            except:
                self._send_json({"address": address, "balance": 0})
        else:
            self._send_error(400, "Address required")
    
    def _send_transaction(self, body):
        """Отправка транзакции"""
        try:
            data = json.loads(body)
            tx_data = {
                "from": data.get('from'),
                "to": data.get('to'),
                "value": hex(int(data.get('amount', 0) * 10**18)),
                "gas": "0x5208",
                "gasPrice": "0x3b9aca00"
            }
            rpc_body = json.dumps({"jsonrpc":"2.0","method":"eth_sendTransaction","params":[tx_data],"id":1}).encode()
            req = urllib.request.Request(RPC_URL, data=rpc_body, headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                self._send_json({"success": True, "tx_hash": result.get('result')})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)})
    
    def _mine_block(self, body):
        """Майнинг блока"""
        try:
            data = json.loads(body)
            miner = data.get('miner', '0x40e908721295de4a5cbc775abac8909781aeeea8')
            rpc_body = json.dumps({"jsonrpc":"2.0","method":"eth_mining","params":[miner],"id":1}).encode()
            req = urllib.request.Request(RPC_URL, data=rpc_body, headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                self._send_json({"success": True, "result": result.get('result')})
        except:
            self._send_json({"success": False})
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_error(self, code, message):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

# HTML страница
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
    <div id="status" class="online">🔄 Connecting...</div>
    <div class="info">📦 Height: <span id="height">?</span></div>
    <div class="info">🔗 Chain ID: <span id="chainId">1337</span></div>
    <button onclick="loadBlocks()">🔄 Refresh</button>
    <hr>
    <h2>💰 Send Transaction</h2>
    <input type="text" id="toAddr" placeholder="Recipient address (0x...)">
    <input type="number" id="amount" placeholder="Amount (ABS)">
    <button onclick="sendTx()">Send</button>
    <div id="txResult"></div>
    <h2>📦 Latest Blocks</h2>
    <div id="blocks">Loading...</div>
    <script>
        async function rpcCall(method, params=[]) {
            const res = await fetch('/rpc', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({jsonrpc: '2.0', method, params, id: 1})
            });
            const data = await res.json();
            return data.result;
        }
        
        async function loadBlocks() {
            const blocksDiv = document.getElementById('blocks');
            blocksDiv.innerHTML = 'Loading blocks...';
            try {
                const res = await fetch('/api/blocks');
                const data = await res.json();
                let html = '';
                for (const block of data.blocks.reverse()) {
                    html += `<div class="block">
                        <b>🔷 Block #${block.height}</b>
                        <div>Hash: ${block.block_hash?.substring(0, 30)}...</div>
                        <div>Miner: ${block.miner?.substring(0, 20)}...</div>
                        <div>📝 Transactions: ${block.transaction_count || 0}</div>
                    </div>`;
                }
                blocksDiv.innerHTML = html || '<p>No blocks</p>';
                document.getElementById('height').innerText = data.total;
                document.getElementById('status').innerHTML = '✅ Connected to node';
            } catch(e) {
                blocksDiv.innerHTML = '<p>Error loading blocks</p>';
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
                const res = await fetch('/api/transaction/send', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({from: '0x40e908721295de4a5cbc775abac8909781aeeea8', to: to, amount: parseFloat(amount)})
                });
                const data = await res.json();
                document.getElementById('txResult').innerHTML = data.success ? '✅ Tx sent: ' + data.tx_hash : '❌ Failed';
                setTimeout(loadBlocks, 2000);
            } catch(e) {
                document.getElementById('txResult').innerHTML = '❌ Error';
            }
        }
        
        loadBlocks();
        setInterval(loadBlocks, 5000);
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    print("=" * 50)
    print("🌐 Blockchain Explorer with RPC Proxy (FIXED)")
    print("=" * 50)
    print("📍 URL: http://localhost:8080")
    print("🔄 RPC Proxy: /rpc -> http://localhost:8545")
    print("=" * 50)
    print("✅ Server running! Open http://localhost:8080")
    print("=" * 50)
    
    server = HTTPServer(('0.0.0.0', 8080), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
