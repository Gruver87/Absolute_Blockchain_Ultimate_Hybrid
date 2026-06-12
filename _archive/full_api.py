#!/usr/bin/env python3
"""Full API - все эндпоинты для Explorer"""

import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = "blockchain.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

class FullAPIHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = self.path
        
        # GET /api/stats
        if path == '/api/stats':
            try:
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM blocks")
                total = c.fetchone()[0]
                conn.close()
                self._send_json({"blocks": total, "total_blocks": total})
            except Exception as e:
                self._send_error(str(e))
        
        # GET /api/block/latest
        elif path == '/api/block/latest':
            try:
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM blocks ORDER BY number DESC LIMIT 1")
                row = c.fetchone()
                conn.close()
                if row:
                    self._send_json({
                        "number": row[0],
                        "hash": row[1],
                        "parent_hash": row[2],
                        "timestamp": row[3],
                        "tx_count": row[4],
                        "miner": row[5]
                    })
                else:
                    self._send_json({"error": "No blocks"}, 404)
            except Exception as e:
                self._send_error(str(e))
        
        # GET /api/block/{number}
        elif path.startswith('/api/block/'):
            try:
                num = int(path.split('/')[-1])
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM blocks WHERE number = ?", (num,))
                row = c.fetchone()
                conn.close()
                if row:
                    self._send_json({
                        "number": row[0],
                        "hash": row[1],
                        "parent_hash": row[2],
                        "timestamp": row[3],
                        "tx_count": row[4],
                        "miner": row[5]
                    })
                else:
                    self._send_json({"error": f"Block {num} not found"}, 404)
            except:
                self._send_json({"error": "Invalid block number"}, 400)
        
        # GET /api/blocks/latest?limit=10
        elif path.startswith('/api/blocks/latest'):
            try:
                limit = 10
                if '?' in path:
                    qs = path.split('?')[1]
                    for param in qs.split('&'):
                        if param.startswith('limit='):
                            limit = int(param.split('=')[1])
                
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM blocks ORDER BY number DESC LIMIT ?", (limit,))
                rows = c.fetchall()
                conn.close()
                
                blocks = [{"number": r[0], "hash": r[1], "timestamp": r[3], "tx_count": r[4], "miner": r[5]} for r in rows]
                self._send_json({"blocks": blocks})
            except Exception as e:
                self._send_error(str(e))
        
        # Health check
        elif path == '/api/health':
            self._send_json({"status": "ok"})
        
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_error(self, message, status=500):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

if __name__ == "__main__":
    print("=" * 50)
    print("🌐 FULL API on port 8081")
    print("=" * 50)
    print("📍 GET /api/stats")
    print("📍 GET /api/block/latest")
    print("📍 GET /api/block/{number}")
    print("📍 GET /api/blocks/latest?limit=10")
    print("📍 GET /api/health")
    print("=" * 50)
    print("✅ API running! Press Ctrl+C to stop")
    print("=" * 50)
    
    server = HTTPServer(('0.0.0.0', 8081), FullAPIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
