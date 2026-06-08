#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETHERSCAN-CLONE API v3 - полные данные для детальных страниц"""

import json
import sqlite3
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DB_PATH = "blockchain.db"

def get_conn():
    return sqlite3.connect(DB_PATH, timeout=30)

class EtherscanAPI(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = self.path
        
        try:
            # GET /api/health
            if path == '/api/health':
                self._send_json({"status": "ok"})
            
            # GET /api/stats
            elif path == '/api/stats':
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM blocks")
                total_blocks = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM transactions")
                total_txs = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM accounts")
                total_accounts = c.fetchone()[0]
                conn.close()
                self._send_json({
                    "total_blocks": total_blocks,
                    "total_transactions": total_txs,
                    "total_addresses": total_accounts,
                    "chain_id": 1337
                })
            
            # GET /api/height
            elif path == '/api/height':
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT MAX(number) FROM blocks")
                height = c.fetchone()[0] or 0
                conn.close()
                self._send_json({"height": height})
            
            # GET /api/block/latest
            elif path == '/api/block/latest':
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM blocks ORDER BY number DESC LIMIT 1")
                row = c.fetchone()
                conn.close()
                if row:
                    self._send_json({
                        "number": row[0], "hash": row[1], "parent_hash": row[2],
                        "timestamp": row[3], "miner": row[4], "tx_count": row[5],
                        "gas_used": row[6] if len(row) > 6 else 0,
                        "gas_limit": row[7] if len(row) > 7 else 30000000,
                        "size": row[8] if len(row) > 8 else 0
                    })
                else:
                    self._send_json({"error": "No blocks"}, 404)
            
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
                            "number": row[0], "hash": row[1], "parent_hash": row[2],
                            "timestamp": row[3], "miner": row[4], "tx_count": row[5],
                            "gas_used": row[6] if len(row) > 6 else 0,
                            "gas_limit": row[7] if len(row) > 7 else 30000000,
                            "size": row[8] if len(row) > 8 else 0
                        })
                    else:
                        self._send_json({"error": f"Block {num} not found"}, 404)
                except:
                    self._send_json({"error": "Invalid block number"}, 400)
            
            # GET /api/blocks/latest?limit=15
            elif path.startswith('/api/blocks/latest'):
                limit = 15
                if '?' in path:
                    qs = path.split('?')[1]
                    for param in qs.split('&'):
                        if param.startswith('limit='):
                            limit = int(param.split('=')[1])
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT number, hash, timestamp, tx_count, miner, gas_used FROM blocks ORDER BY number DESC LIMIT ?", (limit,))
                rows = c.fetchall()
                conn.close()
                blocks = [{"number": r[0], "hash": r[1], "timestamp": r[2], "tx_count": r[3], "miner": r[4], "gas_used": r[5] if len(r) > 5 else 0} for r in rows]
                self._send_json({"blocks": blocks})
            
            # GET /api/tx/{hash}
            elif path.startswith('/api/tx/'):
                tx_hash = path.split('/')[-1]
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT hash, block_number, from_addr, to_addr, value, gas_price, gas_limit, gas_used, status, timestamp FROM transactions WHERE hash = ?", (tx_hash,))
                row = c.fetchone()
                conn.close()
                if row:
                    self._send_json({
                        "hash": row[0], "block": row[1], "from": row[2], "to": row[3],
                        "value": row[4], "gas_price": row[5], "gas_limit": row[6],
                        "gas_used": row[7] or 21000, "status": "success" if row[8] == 1 else "pending",
                        "timestamp": row[9]
                    })
                else:
                    self._send_json({"error": f"Transaction {tx_hash} not found"}, 404)
            
            # GET /api/address/{address}
            elif path.startswith('/api/address/'):
                addr = path.split('/')[-1]
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT balance, tx_count FROM accounts WHERE address = ?", (addr,))
                row = c.fetchone()
                c.execute("SELECT hash, block_number, from_addr, to_addr, value, timestamp FROM transactions WHERE from_addr = ? OR to_addr = ? ORDER BY block_number DESC LIMIT 20", (addr, addr))
                txs = c.fetchall()
                conn.close()
                self._send_json({
                    "address": addr,
                    "balance": row[0] if row else "0",
                    "tx_count": row[1] if row else 0,
                    "transactions": [{"hash": tx[0], "block": tx[1], "from": tx[2], "to": tx[3], "value": tx[4], "timestamp": tx[5]} for tx in txs]
                })
            
            # GET /api/search?q={query}
            elif path.startswith('/api/search'):
                from urllib.parse import parse_qs, urlparse
                parsed = urlparse(path)
                params = parse_qs(parsed.query)
                q = params.get('q', [''])[0]
                
                if not q:
                    self._send_json({"error": "No query"}, 400)
                    return
                
                conn = get_conn()
                c = conn.cursor()
                
                # По номеру блока
                if q.isdigit():
                    c.execute("SELECT number, hash FROM blocks WHERE number = ?", (int(q),))
                    row = c.fetchone()
                    if row:
                        conn.close()
                        self._send_json({"type": "block", "data": {"number": row[0], "hash": row[1]}})
                        return
                
                # По хэшу транзакции
                if q.startswith("0x") and len(q) == 66:
                    c.execute("SELECT hash, block_number FROM transactions WHERE hash = ?", (q,))
                    row = c.fetchone()
                    if row:
                        conn.close()
                        self._send_json({"type": "transaction", "data": {"hash": row[0], "block": row[1]}})
                        return
                
                # По адресу
                if q.startswith("0x") and len(q) == 42:
                    c.execute("SELECT address FROM accounts WHERE address = ?", (q,))
                    row = c.fetchone()
                    if row:
                        conn.close()
                        self._send_json({"type": "address", "data": {"address": row[0]}})
                        return
                
                conn.close()
                self._send_json({"type": "not_found", "query": q}, 404)
            
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
    print("🌐 ETHERSCAN-CLONE API v3")
    print("=" * 60)
    print("📍 http://localhost:8081")
    print("📡 GET /api/block/{number}")
    print("📡 GET /api/tx/{hash}")
    print("📡 GET /api/address/{address}")
    print("📡 GET /api/search?q={query}")
    print("📡 GET /api/blocks/latest?limit=15")
    print("=" * 60)
    print("✅ API running! Press Ctrl+C to stop")
    print("=" * 60)
    
    server = ThreadingHTTPServer(('0.0.0.0', 8081), EtherscanAPI)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
