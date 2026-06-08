#!/usr/bin/env python3
"""Absolute Blockchain - Universal CORS Proxy (работает с любым форматом блоков)"""

import json
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

RPC_URL = "http://localhost:8545"
MAX_BLOCKS = 15

HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Absolute Blockchain Explorer</title>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: monospace; background: #0a0a0a; color: #0f0; padding: 20px; }
        h1 { color: #0f0; text-align: center; }
        .online { background: #0a3a0a; border: 1px solid #0f0; padding: 10px; margin: 10px 0; text-align: center; }
        .offline { background: #3a0a0a; border: 1px solid #f00; padding: 10px; margin: 10px 0; text-align: center; }
        .block { border: 1px solid #0f0; margin: 10px 0; padding: 10px; border-radius: 5px; }
        .info { display: inline-block; margin: 5px; padding: 5px 10px; background: #1a1a1a; border-radius: 5px; }
        button { background: #0a0a0a; color: #0f0; border: 1px solid #0f0; padding: 10px; cursor: pointer; }
        .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #888; }
    </style>
</head>
<body>
    <h1>🔗 Absolute Blockchain Explorer</h1>
    <div id="status" class="offline">🔄 Connecting...</div>
    <div class="info">📦 Height: <span id="height">?</span></div>
    <div class="info">🔗 Chain ID: 1337</div>
    <div class="info">⛏️ Mining: Active (15s)</div>
    <button onclick="refresh()">🔄 Refresh</button>
    <hr>
    <div id="blocks">Loading blocks...</div>
    <div class="footer">Absolute Blockchain Ultimate | RPC: 8545</div>

    <script>
        async function getBlocks() {
            try {
                const res = await fetch('/api/blocks');
                const data = await res.json();
                return data;
            } catch(e) {
                console.error('Get blocks failed:', e);
                return null;
            }
        }
        
        async function refresh() {
            try {
                const blocksData = await getBlocks();
                if (blocksData && blocksData.blocks) {
                    document.getElementById('status').innerHTML = '✅ Connected to node';
                    document.getElementById('status').className = 'online';
                    document.getElementById('height').innerText = blocksData.total;
                    
                    let html = '';
                    for (const block of blocksData.blocks) {
                        html += '<div class="block">' +
                            '<b>🔷 Block #' + block.height + '</b>' +
                            '<div>Hash: ' + (block.hash ? block.hash.substring(0, 30) : 'N/A') + '...</div>' +
                            '<div>Miner: ' + (block.miner ? block.miner.substring(0, 25) : 'Unknown') + '...</div>' +
                            '<div>📝 Transactions: ' + (block.tx_count || 0) + '</div>' +
                            '</div>';
                    }
                    document.getElementById('blocks').innerHTML = html || '<p>No blocks found</p>';
                } else {
                    throw new Error('No data');
                }
            } catch(e) {
                document.getElementById('status').innerHTML = '❌ Node offline';
                document.getElementById('status').className = 'offline';
                document.getElementById('blocks').innerHTML = '<p>Cannot connect to node.</p>';
                document.getElementById('height').innerText = '?';
            }
        }
        
        refresh();
        setInterval(refresh, 5000);
    </script>
</body>
</html>"""

def parse_block(block_data):
    """Универсальный парсер блока - работает с любым форматом"""
    # Если пришла строка - пробуем распарсить JSON
    if isinstance(block_data, str):
        try:
            block_data = json.loads(block_data)
        except:
            pass
    
    # Если это не словарь - возвращаем None
    if not isinstance(block_data, dict):
        return None
    
    # Пробуем извлечь height из разных возможных полей
    height = None
    if 'height' in block_data:
        height = block_data['height']
    elif 'number' in block_data:
        number = block_data['number']
        if isinstance(number, str) and number.startswith('0x'):
            height = int(number, 16)
        else:
            height = number
    
    # Пробуем извлечь hash
    block_hash = block_data.get('hash', block_data.get('block_hash', ''))
    
    # Пробуем извлечь miner
    miner = block_data.get('miner', block_data.get('validator', ''))
    
    # Пробуем извлечь количество транзакций
    txs = block_data.get('transactions', [])
    tx_count = len(txs) if isinstance(txs, list) else 0
    
    if height is None:
        return None
    
    return {
        'height': height,
        'hash': block_hash,
        'miner': miner,
        'tx_count': tx_count
    }

class UniversalProxyHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._send_html(HTML)
        elif self.path == '/api/blocks':
            self._get_blocks()
        elif self.path == '/api/stats':
            self._get_stats()
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        if self.path == '/api':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length else b'{}'
            self._proxy_rpc(body)
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _get_blocks(self):
        """Получение последних блоков с универсальным парсером"""
        try:
            # Получаем текущую высоту
            body = json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                result = data.get('result', '0x0')
                if isinstance(result, str) and result.startswith('0x'):
                    current = int(result, 16)
                else:
                    current = int(result)
            
            # Получаем последние блоки
            blocks = []
            start = max(0, current - MAX_BLOCKS + 1)
            for height in range(current, start - 1, -1):
                hex_height = hex(height)
                body = json.dumps({"jsonrpc": "2.0", "method": "eth_getBlockByNumber", "params": [hex_height, True], "id": 1}).encode()
                req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type': 'application/json'})
                try:
                    with urllib.request.urlopen(req, timeout=10) as response:
                        block_data = json.loads(response.read().decode())
                        block_result = block_data.get('result')
                        if block_result:
                            parsed = parse_block(block_result)
                            if parsed:
                                blocks.append(parsed)
                except Exception as e:
                    print(f"Error getting block {height}: {e}")
            
            self._send_json({"blocks": blocks, "total": current})
        except Exception as e:
            print(f"Error in _get_blocks: {e}")
            self._send_json({"error": str(e), "blocks": [], "total": 0}, 500)
    
    def _get_stats(self):
        try:
            body = json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                result = data.get('result', '0x0')
                if isinstance(result, str) and result.startswith('0x'):
                    current = int(result, 16)
                else:
                    current = int(result)
                self._send_json({"blocks": current, "version": "54.0", "mempool_size": 0})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
    
    def _proxy_rpc(self, body):
        try:
            req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as response:
                result = response.read().decode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(result.encode())
        except Exception as e:
            self._send_json({"error": f"RPC error: {str(e)}"}, 500)
    
    def _send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

if __name__ == '__main__':
    print("=" * 50)
    print("🌐 ABSOLUTE BLOCKCHAIN EXPLORER (UNIVERSAL)")
    print("=" * 50)
    print(f"📍 URL: http://localhost:8080")
    print(f"🔄 GET /api/blocks - последние {MAX_BLOCKS} блоков")
    print(f"🔄 Универсальный парсер - работает с любым форматом")
    print("=" * 50)
    print("✅ Server running! Open http://localhost:8080")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    server = HTTPServer(('0.0.0.0', 8080), UniversalProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
