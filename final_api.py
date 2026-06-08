#!/usr/bin/env python3
"""FINAL API - ПОЛНАЯ ВЕРСИЯ со всеми эндпоинтами"""

import json
import sqlite3
import urllib.request
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DB_PATH = "blockchain.db"
RPC_URL = "http://localhost:8545"

def get_conn():
    return sqlite3.connect(DB_PATH, timeout=30)

def rpc_call(method, params):
    try:
        data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
        req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode()).get("result")
    except Exception as e:
        print(f"RPC error: {e}")
        return None

class FinalAPIHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = self.path
        
        try:
            # GET /api/health
            if path == '/api/health':
                self._safe_send_json({"status": "ok", "timestamp": int(time.time())})
            
            # GET /api/height - ЖИВАЯ ВЫСОТА ИЗ RPC
            elif path == '/api/height':
                height_hex = rpc_call("eth_blockNumber", [])
                if height_hex:
                    height = int(height_hex, 16)
                    self._safe_send_json({"height": height})
                else:
                    self._safe_send_json({"height": 0, "error": "RPC failed"}, 500)
            
            # GET /api/stats - ИЗ БД
            elif path == '/api/stats':
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM blocks")
                total = c.fetchone()[0]
                conn.close()
                self._safe_send_json({"blocks": total, "total_blocks": total})
            
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
                self._safe_send_json({"blocks": blocks})
            
            # GET /api/tx/{hash}
            elif path.startswith('/api/tx/'):
                tx_hash = path.split('/')[-1]
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM transactions WHERE hash = ?", (tx_hash,))
                row = c.fetchone()
                conn.close()
                if row:
                    self._safe_send_json({
                        "hash": row[0],
                        "block_number": row[1],
                        "from": row[2],
                        "to": row[3],
                        "value": row[4]
                    })
                else:
                    self._safe_send_json({"error": f"Transaction {tx_hash} not found"}, 404)
            
            # GET /api/address/{address}
            elif path.startswith('/api/address/'):
                addr = path.split('/')[-1]
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM accounts WHERE address = ?", (addr,))
                row = c.fetchone()
                conn.close()
                if row:
                    self._safe_send_json({
                        "address": addr,
                        "balance": row[1],
                        "tx_count": row[2],
                        "last_seen": row[3]
                    })
                else:
                    self._safe_send_json({"address": addr, "balance": "0x0", "tx_count": 0})
            
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
        except Exception as e:
            print(f"Send error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🌐 FINAL API (FULL VERSION)")
    print("=" * 60)
    print("📍 http://localhost:8081")
    print("📡 Endpoints:")
    print("   GET /api/health")
    print("   GET /api/height      - живая высота из RPC")
    print("   GET /api/stats       - статистика из БД")
    print("   GET /api/block/latest")
    print("   GET /api/block/{number}")
    print("   GET /api/blocks/latest?limit=10")
    print("   GET /api/tx/{hash}")
    print("   GET /api/address/{address}")
    print("=" * 60)
    print("✅ API running! Press Ctrl+C to stop")
    print("=" * 60)
    
    server = ThreadingHTTPServer(('0.0.0.0', 8081), FinalAPIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
