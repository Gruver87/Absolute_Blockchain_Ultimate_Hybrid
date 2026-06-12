#!/usr/bin/env python3
"""Absolute Blockchain - STABLE Proxy v2 (RPC-safe, retry, защита)"""

import json
import urllib.request
import urllib.error
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

RPC_URL = "http://localhost:8545"
MAX_BLOCKS = 10
MAX_RETRIES = 3
RETRY_DELAY = 0.3

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
    <h1>🔗 Absolute Blockchain Explorer (STABLE)</h1>
    <div id="status" class="offline">🔄 Connecting...</div>
    <div class="info">📦 Height: <span id="height">?</span></div>
    <div class="info">🔗 Chain ID: 1337</div>
    <div class="info">⛏️ Mining: Active</div>
    <button onclick="refresh()">🔄 Refresh</button>
    <hr>
    <div id="blocks">Loading...</div>
    <div class="footer">Absolute Blockchain Ultimate | RPC: 8545 | Stable v2</div>

    <script>
        let loading = false;
        
        async function refresh() {
            if (loading) return;
            loading = true;
            
            try {
                const res = await fetch('/api/stable');
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
                    throw new Error('Invalid response');
                }
            } catch(e) {
                document.getElementById('status').innerHTML = '❌ Node offline';
                document.getElementById('status').className = 'offline';
                document.getElementById('blocks').innerHTML = '<p>Cannot connect to node.</p>';
                document.getElementById('height').innerText = '?';
            }
            
            loading = false;
        }
        
        refresh();
        setInterval(refresh, 5000);
    </script>
</body>
</html>"""

def safe_rpc_call(method, params, retries=MAX_RETRIES):
    """RPC вызов с retry и защитой"""
    for attempt in range(retries):
        try:
            body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
            req = urllib.request.Request(RPC_URL, data=body, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                return data.get('result')
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
            else:
                print(f"RPC call failed after {retries} attempts: {method}")
                return None
    return None

def safe_parse_block(block):
    """Безопасный парсинг блока - защита от str/None/битых данных"""
    if not block or not isinstance(block, dict):
        return None
    
    try:
        # Извлекаем высоту
        height = None
        if 'number' in block:
            num = block['number']
            if isinstance(num, str) and num.startswith('0x'):
                height = int(num, 16)
            else:
                height = int(num) if num is not None else None
        elif 'height' in block:
            height = int(block['height']) if block['height'] is not None else None
        
        if height is None:
            return None
        
        return {
            'height': height,
            'hash': str(block.get('hash', block.get('block_hash', ''))),
            'miner': str(block.get('miner', block.get('validator', '')))
        }
    except Exception as e:
        print(f"Parse block error: {e}")
        return None

class StableHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._safe_send(HTML, 200, 'text/html')
        elif self.path == '/api/stable':
            self._get_stable_data()
        else:
            self._safe_send({"error": "Not found"}, 404)
    
    def do_OPTIONS(self):
        self._safe_send({}, 200, headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, OPTIONS'})
    
    def _get_stable_data(self):
        """Стабильные данные с RPC-safe wrapper"""
        try:
            # Получаем высоту с retry
            height_hex = safe_rpc_call("eth_blockNumber", [])
            if not height_hex:
                self._safe_send({"height": 0, "blocks": [], "error": "RPC failed"}, 200)
                return
            
            height = int(height_hex, 16) if isinstance(height_hex, str) and height_hex.startswith('0x') else int(height_hex)
            
            # Получаем последние блоки
            blocks = []
            start = max(0, height - MAX_BLOCKS + 1)
            
            for h in range(height, start - 1, -1):
                hex_h = hex(h)
                block_data = safe_rpc_call("eth_getBlockByNumber", [hex_h, True])
                
                if block_data:
                    block = block_data.get('result') if isinstance(block_data, dict) else block_data
                    parsed = safe_parse_block(block)
                    if parsed:
                        blocks.append(parsed)
                else:
                    # Пропускаем битые блоки
                    pass
            
            self._safe_send({"height": height, "blocks": blocks, "status": "ok"})
            
        except Exception as e:
            print(f"Error in _get_stable_data: {e}")
            self._safe_send({"height": 0, "blocks": [], "error": str(e)}, 500)
    
    def _safe_send(self, data, status=200, content_type='application/json', headers=None):
        """Безопасная отправка с защитой от ConnectionAbortedError"""
        try:
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Access-Control-Allow-Origin', '*')
            if headers:
                for k, v in headers.items():
                    self.send_header(k, v)
            self.end_headers()
            
            if content_type == 'application/json':
                self.wfile.write(json.dumps(data).encode())
            else:
                self.wfile.write(data.encode() if isinstance(data, str) else data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # Браузер закрыл соединение — просто игнорируем
            pass
        except Exception as e:
            print(f"Safe send error: {e}")

if __name__ == '__main__':
    print("=" * 50)
    print("🌐 ABSOLUTE BLOCKCHAIN EXPLORER (STABLE v2)")
    print("=" * 50)
    print("📍 URL: http://localhost:8080")
    print("🔄 RPC-safe wrapper | Retry | Защита от битых блоков")
    print("=" * 50)
    print("✅ Server running! Open http://localhost:8080")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    server = HTTPServer(('0.0.0.0', 8080), StableHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
