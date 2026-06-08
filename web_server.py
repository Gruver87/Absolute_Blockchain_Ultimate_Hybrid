# web_server.py - Simple web server with CORS headers
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

os.chdir('web')
print("🌐 Web server running on http://localhost:8080")
print("📊 Open in browser: http://localhost:8080")
HTTPServer(('0.0.0.0', 8080), CORSRequestHandler).serve_forever()
