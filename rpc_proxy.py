# rpc_proxy.py - FIXED with error handling
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
                
                # FIXED: Handle connection errors gracefully
                try:
                    self.wfile.write(response.content)
                except (BrokenPipeError, ConnectionAbortedError):
                    pass  # Client disconnected, ignore
                    
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                try:
                    self.wfile.write(json.dumps({'error': str(e)}).encode())
                except (BrokenPipeError, ConnectionAbortedError):
                    pass
    
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


