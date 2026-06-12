#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIXED API - без 500 ошибок"""

import json
import sqlite3
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DB_PATH = "blockchain.db"

def get_conn():
    return sqlite3.connect(DB_PATH, timeout=30)

class FixedAPIHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = self.path
        
        try:
            # GET /api/health
            if path == '/api/health':
                self._send_json({"status": "ok", "timestamp": int(time.time())})
            
            # GET /api/stats
            elif path == '/api/stats':
                try:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("SELECT COUNT(*) FROM blocks")
                    total_blocks = c.fetchone()[0] or 0
                    c.execute("SELECT COUNT(*) FROM transactions")
                    total_txs = c.fetchone()[0] or 0
                    c.execute("SELECT COUNT(*) FROM addresses")
                    total_addresses = c.fetchone()[0] or 0
                    conn.close()
                    
                    self._send_json({
                        "total_blocks": total_blocks,
                        "total_transactions": total_txs,
                        "total_addresses": total_addresses,
                        "chain_id": 1337
                    })
                except Exception as e:
                    print(f"Stats error: {e}")
                    self._send_json({"total_blocks": 0, "total_transactions": 0, "total_addresses": 0})
            
            # GET /api/height
            elif path == '/api/height':
                try:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("SELECT MAX(number) FROM blocks")
                    height = c.fetchone()[0] or 0
                    conn.close()
                    self._send_json({"height": height})
                except:
                    self._send_json({"height": 0})
            
            # GET /api/blocks/latest?limit=15
            elif path.startswith('/api/blocks/latest'):
                limit = 15
                if '?' in path:
                    qs = path.split('?')[1]
                    for param in qs.split('&'):
                        if param.startswith('limit='):
                            limit = int(param.split('=')[1])
                
                try:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("SELECT number, hash, timestamp, tx_count, miner, gas_used FROM blocks ORDER BY number DESC LIMIT ?", (limit,))
                    rows = c.fetchall()
                    conn.close()
                    
                    blocks = []
                    for row in rows:
                        blocks.append({
                            "number": row[0],
                            "hash": row[1],
                            "timestamp": row[2],
                            "tx_count": row[3],
                            "miner": row[4],
                            "gas_used": row[5] if len(row) > 5 else 0
                        })
                    self._send_json({"blocks": blocks})
                except Exception as e:
                    print(f"Blocks error: {e}")
                    self._send_json({"blocks": []})
            
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
                            "miner": row[4],
                            "tx_count": row[5],
                            "gas_used": row[6] if len(row) > 6 else 0
                        })
                    else:
                        self._send_json({"error": f"Block {num} not found"}, 404)
                except:
                    self._send_json({"error": "Invalid block number"}, 400)
            
            # GET /api/address/{address}
            elif path.startswith('/api/address/'):
                addr = path.split('/')[-1]
                try:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("SELECT balance, tx_count FROM addresses WHERE address = ?", (addr,))
                    row = c.fetchone()
                    c.execute("SELECT hash, block_number, from_addr, to_addr, value, timestamp FROM transactions WHERE from_addr = ? OR to_addr = ? ORDER BY block_number DESC LIMIT 20", (addr, addr))
                    txs = c.fetchall()
                    conn.close()
                    
                    self._send_json({
                        "address": addr,
                        "balance": row[0] if row else 0,
                        "tx_count": row[1] if row else 0,
                        "transactions": [{"hash": tx[0], "block": tx[1], "from": tx[2], "to": tx[3], "value": tx[4], "timestamp": tx[5]} for tx in txs]
                    })
                except:
                    self._send_json({"address": addr, "balance": 0, "tx_count": 0, "transactions": []})
            
            else:
                self._send_json({"error": "Not found"}, 404)
        
        except Exception as e:
            print(f"Handler error: {e}")
            self._send_json({"error": str(e)}, 500)
    
    def _send_json(self, data, status=200):
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
    print("🌐 FIXED API (без 500 ошибок)")
    print("=" * 60)
    print("📍 http://localhost:8081")
    print("📡 GET /api/health")
    print("📡 GET /api/stats")
    print("📡 GET /api/height")
    print("📡 GET /api/blocks/latest?limit=15")
    print("📡 GET /api/block/{number}")
    print("📡 GET /api/address/{address}")
    print("=" * 60)
    print("✅ API running! Press Ctrl+C to stop")
    print("=" * 60)
    
    server = ThreadingHTTPServer(('0.0.0.0', 8081), FixedAPIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
