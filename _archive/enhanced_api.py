#!/usr/bin/env python3
"""Enhanced API - с метриками лага и производительностью"""

import json
import sqlite3
import urllib.request
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DB_PATH = "blockchain.db"
RPC_URL = "http://localhost:8545"
START_TIME = time.time()

def get_conn():
    return sqlite3.connect(DB_PATH, timeout=30)

def rpc_call(method, params):
    try:
        data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
        req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode()).get("result")
    except:
        return None

def get_node_height():
    height_hex = rpc_call("eth_blockNumber", [])
    if height_hex:
        return int(height_hex, 16)
    return 0

def get_db_height():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT MAX(number) FROM blocks")
    result = c.fetchone()[0] or 0
    conn.close()
    return result

def get_total_blocks():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM blocks")
    result = c.fetchone()[0] or 0
    conn.close()
    return result

class EnhancedAPIHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = self.path
        
        try:
            # GET /api/health
            if path == '/api/health':
                self._safe_send_json({
                    "status": "ok",
                    "uptime": int(time.time() - START_TIME)
                })
            
            # GET /api/height - живая высота + лаг
            elif path == '/api/height':
                node_h = get_node_height()
                db_h = get_db_height()
                self._safe_send_json({
                    "height": node_h,
                    "db_height": db_h,
                    "lag": node_h - db_h,
                    "synced": node_h - db_h < 5
                })
            
            # GET /api/stats - полная статистика
            elif path == '/api/stats':
                node_h = get_node_height()
                db_h = get_db_height()
                total_blocks = get_total_blocks()
                self._safe_send_json({
                    "height": node_h,
                    "total_blocks": total_blocks,
                    "db_height": db_h,
                    "lag": node_h - db_h,
                    "synced": node_h - db_h < 5,
                    "uptime": int(time.time() - START_TIME)
                })
            
            # GET /api/block/latest
            elif path == '/api/block/latest':
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM blocks ORDER BY number DESC LIMIT 1")
                row = c.fetchone()
                conn.close()
                if row:
                    self._safe_send_json({
                        "number": row[0],
                        "hash": row[1],
                        "parent_hash": row[2],
                        "timestamp": row[3],
                        "tx_count": row[4],
                        "miner": row[5]
                    })
                else:
                    self._safe_send_json({"error": "No blocks"}, 404)
            
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
                        self._safe_send_json({
                            "number": row[0],
                            "hash": row[1],
                            "parent_hash": row[2],
                            "timestamp": row[3],
                            "tx_count": row[4],
                            "miner": row[5]
                        })
                    else:
                        self._safe_send_json({"error": f"Block {num} not found"}, 404)
                except:
                    self._safe_send_json({"error": "Invalid block number"}, 400)
            
            # GET /api/blocks/latest?limit=10
            elif path.startswith('/api/blocks/latest'):
                limit = 15
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
                self._safe_send_json({"blocks": blocks})
            
            else:
                self._safe_send_json({"error": "Not found"}, 404)
        
        except Exception as e:
            self._safe_send_json({"error": str(e)}, 500)
    
    def _safe_send_json(self, data, status=200):
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            pass

if __name__ == "__main__":
    print("=" * 60)
    print("🌐 ENHANCED API (with lag metrics)")
    print("=" * 60)
    print("📍 http://localhost:8081")
    print("📡 GET /api/height - returns {height, db_height, lag, synced}")
    print("📡 GET /api/stats - full statistics")
    print("=" * 60)
    print("✅ API running! Press Ctrl+C to stop")
    print("=" * 60)
    
    server = ThreadingHTTPServer(('0.0.0.0', 8081), EnhancedAPIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
