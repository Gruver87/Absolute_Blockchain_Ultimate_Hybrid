#!/usr/bin/env python3
"""Absolute Blockchain - Working Proxy"""

import json
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

RPC_URL = "http://localhost:8545"
MAX_BLOCKS = 10

HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Absolute Blockchain Explorer</title>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="3">
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
    <div class="info">⛏️ Mining: Active</div>
    <button onclick="refresh()">🔄 Refresh</button>
    <hr>
    <div id="blocks">Loading...</div>
    <div class="footer">Absolute Blockchain Ultimate | RPC: 8545</div>

    <script>
        async function refresh() {
            try {
                const res = await fetch('/api/blocks');
                const data = await res.json();
                if (data.height !== undefined) {
                    document.getElementById('status').innerHTML = '✅ Connected to node';
                    document.getElementById('status').className = 'online';
                    document.getElementById('height').innerText = data.height;
                    
                    let html = '';
                    for (const block of (data.blocks || [])) {
                        html += '<div class="block">' +
                            '<b>🔷 Block #' + block.height + '</b>' +
                            '<div>Hash: ' + (block.hash ? block.hash.substring(0, 30) : 'N/A') + '...</div>' +
                            '<div>Miner: ' + (block.miner ? block.miner.substring(0, 25) : 'Unknown') + '</div>' +
                            '</div>';
                    }
                    document.getElementById('blocks').innerHTML = html || '<p>No blocks</p>';
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
    """Парсит блок из любого формата"""
    if isinstance(block_data, str):
        try:
            block_data = json.loads(block_data)
        except:
            return None
    if not isinstance(block_data, dict):
        return None
    
    height = None
    if 'number' in block_data:
        num = block_data['number']
        if isinstance(num, str) and num.startswith('0x'):
            height = int(num, 16)
        else:
            height = num
    elif 'height' in block_data:
        height = block_data['height']
    
    if height is None:
        return None
    
    return {
        'height': height,
        'hash': block_data.get('hash', block_data.get('block_hash', '')),
        'miner': block_data.get('miner', block_data.get('validator', ''))
    }

class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/':
            self._send_html(HTML)
        elif self.path == '/api/blocks':
            self._get_blocks()
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _get_blocks(self):
        try:
            # Получаем высоту
            body = json.dumps({"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}).encode()
            req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                result = data.get('result', '0x0')
                height = int(result, 16) if isinstance(result, str) and result.startswith('0x') else int(result)
            
            # Получаем последние блоки
            blocks = []
            for h in range(height, max(0, height - MAX_BLOCKS), -1):
                hex_h = hex(h)
                body = json.dumps({"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":[hex_h, True],"id":1}).encode()
                req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        block_data = json.loads(response.read().decode())
                        block = block_data.get('result')
                        if block:
                            parsed = parse_block(block)
                            if parsed:
                                blocks.append(parsed)
                except Exception as e:
                    pass
            
            self._send_json({"height": height, "blocks": blocks})
        except Exception as e:
            self._send_json({"error": str(e), "height": 0, "blocks": []}, 500)
    
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
    print("🌐 ABSOLUTE BLOCKCHAIN EXPLORER")
    print("=" * 50)
    print("📍 URL: http://localhost:8080")
    print("=" * 50)
    print("✅ Server running!")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    server = HTTPServer(('0.0.0.0', 8080), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
