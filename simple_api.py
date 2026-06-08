#!/usr/bin/env python3
"""Simple API - без ошибок"""

import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = "blockchain.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

class SimpleHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/api/stats':
            try:
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM blocks")
                total = c.fetchone()[0]
                conn.close()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"blocks": total}).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    print("=" * 40)
    print("🌐 SIMPLE API on port 8081")
    print("=" * 40)
    server = HTTPServer(('0.0.0.0', 8081), SimpleHandler)
    server.serve_forever()
