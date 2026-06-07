# rpc_proxy.py - RPC Proxy with CORS
from http.server import HTTPServer, SimpleHTTPRequestHandler
import requests
import json
import os

class ProxyHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/rpc':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            try:
                response = requests.post(
                    'http://localhost:8545',
                    data=body,
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
                
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(response.content)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        return SimpleHTTPRequestHandler.do_GET(self)
    
    def log_message(self, format, *args):
        pass

# Create web directory if not exists
os.makedirs('web', exist_ok=True)

# Simple index.html if not exists
index_path = 'web/index.html'
if not os.path.exists(index_path):
    with open(index_path, 'w') as f:
        f.write('''<!DOCTYPE html>
<html>
<head><title>Blockchain Explorer</title></head>
<body>
<h1>Absolute Blockchain Explorer</h1>
<p>Loading...</p>
<script>
fetch('/rpc', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1})
})
.then(r => r.json())
.then(data => document.body.innerHTML += `<pre>Block: ${data.result}</pre>`)
.catch(e => document.body.innerHTML += `<p style="color:red">Error: ${e}</p>`);
</script>
</body>
</html>''')

os.chdir('web')
print("=" * 50)
print("🌐 Blockchain Explorer with RPC Proxy")
print("=" * 50)
print("📍 URL: http://localhost:8080")
print("🔄 RPC Proxy: /rpc -> http://localhost:8545")
print("=" * 50)
print("✅ Server running! Open http://localhost:8080")
print("=" * 50)

HTTPServer(('0.0.0.0', 8080), ProxyHandler).serve_forever()
