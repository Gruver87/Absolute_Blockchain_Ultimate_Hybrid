# api_pro.py - Etherscan-совместимый API
import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from db import DB_PATH

class EtherscanHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _get_conn(self):
        return sqlite3.connect(DB_PATH)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        try:
            # Latest block
            if path == "/api/block/latest":
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM blocks ORDER BY number DESC LIMIT 1")
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    self._send_json({
                        "number": row[0],
                        "hash": row[1],
                        "timestamp": row[2],
                        "tx_count": row[3],
                        "miner": row[4]
                    })
                else:
                    self._send_json({"error": "No blocks found"}, 404)
            
            # Block by number
            elif path.startswith("/api/block/"):
                num = int(path.split("/")[-1])
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM blocks WHERE number = ?", (num,))
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    self._send_json({
                        "number": row[0],
                        "hash": row[1],
                        "timestamp": row[2],
                        "tx_count": row[3],
                        "miner": row[4]
                    })
                else:
                    self._send_json({"error": f"Block {num} not found"}, 404)
            
            # Transaction by hash
            elif path.startswith("/api/tx/"):
                tx_hash = path.split("/")[-1]
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM transactions WHERE hash = ?", (tx_hash,))
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    self._send_json({
                        "hash": row[0],
                        "block_number": row[1],
                        "from": row[2],
                        "to": row[3],
                        "value": row[4],
                        "timestamp": row[5]
                    })
                else:
                    self._send_json({"error": f"Transaction {tx_hash} not found"}, 404)
            
            # Address info
            elif path.startswith("/api/address/"):
                addr = path.split("/")[-1]
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM accounts WHERE address = ?", (addr,))
                row = cursor.fetchone()
                
                # Получаем транзакции адреса
                cursor.execute("SELECT * FROM transactions WHERE from_addr = ? OR to_addr = ? ORDER BY block_number DESC LIMIT 20", (addr, addr))
                txs = cursor.fetchall()
                conn.close()
                
                if row:
                    self._send_json({
                        "address": addr,
                        "balance": row[1],
                        "tx_count": row[2],
                        "transactions": [
                            {"hash": tx[0], "block": tx[1], "from": tx[2], "to": tx[3], "value": tx[4], "timestamp": tx[5]}
                            for tx in txs
                        ]
                    })
                else:
                    self._send_json({"address": addr, "balance": 0, "tx_count": 0, "transactions": []})
            
            # Stats
            elif path == "/api/stats":
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM blocks")
                total_blocks = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM transactions")
                total_txs = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM accounts")
                total_accounts = cursor.fetchone()[0]
                conn.close()
                
                self._send_json({
                    "total_blocks": total_blocks,
                    "total_transactions": total_txs,
                    "total_accounts": total_accounts
                })
            
            # Health check
            elif path == "/api/health":
                self._send_json({"status": "ok"})
            
            else:
                self._send_json({"error": "Not found"}, 404)
                
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

if __name__ == "__main__":
    print("=" * 50)
    print("🌐 ETHERSCAN PRO API")
    print("=" * 50)
    print("📍 URL: http://localhost:8081")
    print("📡 Endpoints:")
    print("   GET /api/block/latest")
    print("   GET /api/block/{number}")
    print("   GET /api/tx/{hash}")
    print("   GET /api/address/{address}")
    print("   GET /api/stats")
    print("=" * 50)
    print("✅ API running! Press Ctrl+C to stop")
    print("=" * 50)
    
    server = HTTPServer(('0.0.0.0', 8081), EtherscanHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 API stopped")
