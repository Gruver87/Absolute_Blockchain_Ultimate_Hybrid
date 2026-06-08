#!/usr/bin/env python3
"""Absolute Blockchain - Simple Proxy"""

import json
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

RPC_URL = "http://localhost:8545"

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
    <div class="info">⛏️ Mining: Active</div>
    <button onclick="refresh()">🔄 Refresh</button>
    <hr>
    <div id="blocks">Loading...</div>
    <div class="footer">Absolute Blockchain Ultimate | RPC: 8545</div>

    <script>
        async function refresh() {
            try {
                const res = await fetch('/api/height');
                const data = await res.json();
                if (data.height) {
                    document.getElementById('status').innerHTML = '✅ Connected to node';
                    document.getElementById('status').className = 'online';
                    document.getElementById('height').innerText = data.height;
                    
                    const blocksRes = await fetch('/api/blocks');
                    const blocksData = await blocksRes.json();
                    let html = '';
                    for (const block of (blocksData.blocks || [])) {
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

class ProxyHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/':
            self._send_html(HTML)
        elif self.path == '/api/height':
            self._get_height()
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
    
    def _get_height(self):
        try:
            body = json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                result = data.get('result', '0x0')
                height = int(result, 16) if isinstance(result, str) and result.startswith('0x') else int(result)
                self._send_json({"height": height})
        except Exception as e:
            self._send_json({"error": str(e), "height": 0}, 500)
    
    def _get_blocks(self):
        try:
            # Получаем высоту
            body = json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                result = data.get('result', '0x0')
                height = int(result, 16) if isinstance(result, str) and result.startswith('0x') else int(result)
            
            # Получаем последние 10 блоков
            blocks = []
            start = max(0, height - 9)
            for h in range(height, start - 1, -1):
                hex_h = hex(h)
                body = json.dumps({"jsonrpc": "2.0", "method": "eth_getBlockByNumber", "params": [hex_h, True], "id": 1}).encode()
                req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type': 'application/json'})
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        block_data = json.loads(response.read().decode())
                        block = block_data.get('result')
                        if block and isinstance(block, dict):
                            block_height = int(block.get('number', '0x0'), 16) if isinstance(block.get('number'), str) else block.get('number', 0)
                            blocks.append({
                                'height': block_height,
                                'hash': block.get('hash', ''),
                                'miner': block.get('miner', '')
                            })
                except Exception as e:
                    pass
            
            self._send_json({"blocks": blocks, "height": height})
        except Exception as e:
            self._send_json({"error": str(e), "blocks": []}, 500)
    
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
    print("✅ Server running! Open http://localhost:8080")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    server = HTTPServer(('0.0.0.0', 8080), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
