#!/usr/bin/env python3
"""READ-ONLY API - только SELECT, никогда не пишет"""

import json
import sqlite3
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DB_PATH = "blockchain.db"

def get_conn():
    return sqlite3.connect(DB_PATH, timeout=30)

class ReadOnlyAPI(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = self.path
        
        try:
            if path == '/api/health':
                self._send_json({"status": "ok", "timestamp": int(time.time())})
            
            elif path == '/api/stats':
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM blocks")
                blocks = c.fetchone()[0] or 0
                c.execute("SELECT COUNT(*) FROM transactions")
                txs = c.fetchone()[0] or 0
                c.execute("SELECT COUNT(*) FROM addresses")
                addrs = c.fetchone()[0] or 0
                conn.close()
                self._send_json({
                    "total_blocks": blocks,
                    "total_transactions": txs,
                    "total_addresses": addrs,
                    "chain_id": 1337
                })
            
            elif path == '/api/height':
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT MAX(number) FROM blocks")
                height = c.fetchone()[0] or 0
                conn.close()
                self._send_json({"height": height})
            
            elif path.startswith('/api/blocks/latest'):
                limit = 15
                if '?' in path:
                    qs = path.split('?')[1]
                    for param in qs.split('&'):
                        if param.startswith('limit='):
                            limit = int(param.split('=')[1])
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT number, hash, timestamp, tx_count, miner FROM blocks ORDER BY number DESC LIMIT ?", (limit,))
                rows = c.fetchall()
                conn.close()
                blocks = [{"number": r[0], "hash": r[1], "timestamp": r[2], "tx_count": r[3], "miner": r[4]} for r in rows]
                self._send_json({"blocks": blocks})
            
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
                            "number": row[0], "hash": row[1], "parent_hash": row[2],
                            "timestamp": row[3], "miner": row[4], "tx_count": row[5]
                        })
                    else:
                        self._send_json({"error": f"Block {num} not found"}, 404)
                except:
                    self._send_json({"error": "Invalid block number"}, 400)
            
            else:
                self._send_json({"error": "Not found"}, 404)
        
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
    
    def _send_json(self, data, status=200):
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except:
            pass

if __name__ == "__main__":
    print("=" * 60)
    print("🌐 READ-ONLY API (Production)")
    print("=" * 60)
    print("📍 http://localhost:8081")
    print("=" * 60)
    print("✅ API running! Press Ctrl+C to stop")
    print("=" * 60)
    
    server = ThreadingHTTPServer(('0.0.0.0', 8081), ReadOnlyAPI)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
