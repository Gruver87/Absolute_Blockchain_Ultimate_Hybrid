#!/usr/bin/env python3
"""Etherscan-like API с полноценным поиском"""

import json
import sqlite3
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = "blockchain.db"
START_TIME = time.time()

def get_conn():
    return sqlite3.connect(DB_PATH, timeout=30)

class EtherscanAPI(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        try:
            # Health
            if path == '/api/health':
                self._send_json({"status": "ok", "uptime": int(time.time() - START_TIME)})
            
            # Статистика
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
            
            # Последние блоки
            elif path == '/api/blocks/latest':
                limit = int(query.get('limit', [15])[0])
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT number, hash, timestamp, tx_count, miner FROM blocks ORDER BY number DESC LIMIT ?", (limit,))
                rows = c.fetchall()
                conn.close()
                blocks = [{"number": r[0], "hash": r[1], "timestamp": r[2], "tx_count": r[3], "miner": r[4]} for r in rows]
                self._send_json({"blocks": blocks})
            
            # Блок по номеру
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
                            "timestamp": row[3], "miner": row[5], "tx_count": row[6],
                            "gas_used": row[7], "gas_limit": row[8], "size": row[9]
                        })
                    else:
                        self._send_json({"error": f"Block {num} not found"}, 404)
                except:
                    self._send_json({"error": "Invalid block number"}, 400)
            
            # Транзакция по хэшу
            elif path.startswith('/api/tx/'):
                tx_hash = path.split('/')[-1]
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM transactions WHERE hash = ?", (tx_hash,))
                row = c.fetchone()
                conn.close()
                if row:
                    self._send_json({
                        "hash": row[0], "block_number": row[1], "from": row[2],
                        "to": row[3], "value": row[4], "gas": row[5],
                        "gas_price": row[6], "nonce": row[7], "timestamp": row[9]
                    })
                else:
                    self._send_json({"error": f"Transaction {tx_hash} not found"}, 404)
            
            # Адрес
            elif path.startswith('/api/address/'):
                addr = path.split('/')[-1]
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM accounts WHERE address = ?", (addr,))
                row = c.fetchone()
                c.execute("SELECT hash, block_number, from_addr, to_addr, value, timestamp FROM transactions WHERE from_addr = ? OR to_addr = ? ORDER BY block_number DESC LIMIT 20", (addr, addr))
                txs = c.fetchall()
                conn.close()
                self._send_json({
                    "address": addr,
                    "balance": row[1] if row else "0",
                    "tx_count": row[2] if row else 0,
                    "transactions": [{"hash": tx[0], "block": tx[1], "from": tx[2], "to": tx[3], "value": tx[4], "timestamp": tx[5]} for tx in txs]
                })
            
            # ПОИСК (главная фича Etherscan!)
            elif path == '/api/search' and 'q' in query:
                q = query['q'][0].strip()
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
                    c.execute("SELECT address, balance FROM accounts WHERE address = ?", (q,))
                    row = c.fetchone()
                    if row:
                        conn.close()
                        self._send_json({"type": "address", "data": {"address": row[0], "balance": row[1]}})
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
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            pass

if __name__ == "__main__":
    print("=" * 60)
    print("🌐 ETHERSCAN-LIKE API v2.0")
    print("=" * 60)
    print("📍 http://localhost:8081")
    print("📡 GET /api/search?q={query} - ПОИСК!")
    print("📡 GET /api/block/{number}")
    print("📡 GET /api/tx/{hash}")
    print("📡 GET /api/address/{address}")
    print("📡 GET /api/blocks/latest?limit=15")
    print("=" * 60)
    print("✅ API running! Press Ctrl+C to stop")
    print("=" * 60)
    
    server = ThreadingHTTPServer(('0.0.0.0', 8081), EtherscanAPI)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
