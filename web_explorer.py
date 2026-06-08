#!/usr/bin/env python3
"""Absolute Blockchain - Простой веб-интерфейс"""

import json
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

RPC_URL = "http://localhost:8545"

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Absolute Blockchain Explorer</title>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: monospace; background: #0a0a0a; color: #0f0; padding: 20px; }
        h1 { color: #0f0; text-align: center; }
        .status { background: #0a3a0a; border: 1px solid #0f0; padding: 10px; margin: 10px 0; text-align: center; }
        .block { border: 1px solid #0f0; margin: 10px 0; padding: 10px; border-radius: 5px; }
        .info { display: inline-block; margin: 5px; padding: 5px 10px; background: #1a1a1a; border-radius: 5px; }
        .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #888; }
    </style>
</head>
<body>
    <h1>🔗 Absolute Blockchain Explorer</h1>
    <div id="status" class="status">🔄 Loading...</div>
    <div class="info">📦 Height: <span id="height">?</span></div>
    <div class="info">🔗 Chain ID: <span id="chainId">1337</span></div>
    <div class="info">⛏️ Mining: Active (every 15s)</div>
    <hr>
    <div id="blocks">Loading blocks...</div>
    <div class="footer">Absolute Blockchain Ultimate | RPC: 8545 | Auto-mining active</div>
    
    <script>
        async function rpcCall(method, params=[]) {
            try {
                const res = await fetch('/rpc', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({jsonrpc: '2.0', method, params, id: 1})
                });
                const data = await res.json();
                return data.result;
            } catch(e) {
                console.error(e);
                return null;
            }
        }
        
        async function load() {
            try {
                // Get block number
                const blockNumHex = await rpcCall('eth_blockNumber');
                if (blockNumHex) {
                    const height = parseInt(blockNumHex, 16);
                    document.getElementById('status').innerHTML = '✅ Connected to node';
                    document.getElementById('height').innerText = height;
                    document.getElementById('status').style.background = '#0a3a0a';
                    
                    // Load blocks
                    let html = '';
                    const start = Math.max(0, height - 9);
                    for (let i = height; i >= start; i--) {
                        const block = await rpcCall('eth_getBlockByNumber', ['0x' + i.toString(16), true]);
                        if (block) {
                            html += `<div class="block">
                                <b>🔷 Block #${parseInt(block.number, 16)}</b>
                                <div>Hash: ${block.hash ? block.hash.substring(0, 30) + '...' : 'N/A'}</div>
                                <div>Miner: ${block.miner ? block.miner.substring(0, 25) + '...' : 'Unknown'}</div>
                                <div>📝 Transactions: ${block.transactions?.length || 0}</div>
                                <div>⏱️ Time: ${block.timestamp ? new Date(parseInt(block.timestamp, 16) * 1000).toLocaleTimeString() : 'N/A'}</div>
                            </div>`;
                        }
                    }
                    document.getElementById('blocks').innerHTML = html || '<p>No blocks found</p>';
                } else {
                    throw new Error('No response');
                }
            } catch(e) {
                document.getElementById('status').innerHTML = '❌ Node offline - Make sure node is running on port 8545';
                document.getElementById('status').style.background = '#3a0a0a';
                document.getElementById('blocks').innerHTML = '<p>Cannot connect to blockchain node. Please start node_persistent.py</p>';
            }
        }
        
        load();
        setInterval(load, 5000);
    </script>
</body>
</html>
"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == '/rpc':
            # Проксируем RPC запросы
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length else b'{}'
            try:
                req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    result = response.read().decode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(result.encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    print("=" * 50)
    print("🌐 ABSOLUTE BLOCKCHAIN EXPLORER")
    print("=" * 50)
    print("📍 URL: http://localhost:8080")
    print("🔄 RPC Proxy: /rpc -> http://localhost:8545")
    print("=" * 50)
    print("✅ Server running! Open http://localhost:8080")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    server = HTTPServer(('0.0.0.0', 8080), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
