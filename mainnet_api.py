#!/usr/bin/env python3
"""Mainnet API - Etherscan-совместимый REST API"""

import json
import sqlite3
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = "blockchain.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def safe_send(handler, data, status=200):
    """Безопасная отправка с защитой от разрыва соединения"""
    try:
        handler.send_response(status)
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.end_headers()
        handler.wfile.write(json.dumps(data).encode('utf-8'))
    except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
        pass

class MainnetAPIHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        try:
            # Health check
            if path == "/api/health":
                safe_send(self, {"status": "ok", "timestamp": int(time.time())})
            
            # Статистика сети
            elif path == "/api/stats":
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM blocks")
                total_blocks = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM transactions")
                total_txs = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM accounts")
                total_accounts = cursor.fetchone()[0]
                conn.close()
                
                safe_send(self, {
                    "height": total_blocks,
                    "total_blocks": total_blocks,
                    "total_transactions": total_txs,
                    "total_addresses": total_accounts,
                    "tps": 0,
                    "block_time": 15,
                    "chain_id": 1337
                })
            
            # Последний блок
            elif path == "/api/block/latest":
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM blocks ORDER BY number DESC LIMIT 1")
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    safe_send(self, {
                        "number": row[0],
                        "hash": row[1],
                        "parent_hash": row[2],
                        "timestamp": row[3],
                        "tx_count": row[4],
                        "miner": row[5],
                        "gas_used": row[8],
                        "gas_limit": row[9]
                    })
                else:
                    safe_send(self, {"error": "No blocks found"}, 404)
            
            # Блок по номеру
            elif path.startswith("/api/block/"):
                try:
                    num = int(path.split("/")[-1])
                    conn = get_conn()
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM blocks WHERE number = ?", (num,))
                    row = cursor.fetchone()
                    
                    if row:
                        safe_send(self, {
                            "number": row[0],
                            "hash": row[1],
                            "parent_hash": row[2],
                            "timestamp": row[3],
                            "tx_count": row[4],
                            "miner": row[5],
                            "gas_used": row[8],
                            "gas_limit": row[9]
                        })
                    else:
                        safe_send(self, {"error": f"Block {num} not found"}, 404)
                    conn.close()
                except ValueError:
                    safe_send(self, {"error": "Invalid block number"}, 400)
            
            # Транзакция по хэшу
            elif path.startswith("/api/tx/"):
                tx_hash = path.split("/")[-1]
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM transactions WHERE hash = ?", (tx_hash,))
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    safe_send(self, {
                        "hash": row[0],
                        "block_number": row[1],
                        "from": row[2],
                        "to": row[3],
                        "value": row[4],
                        "gas": row[5],
                        "gas_price": row[6],
                        "nonce": row[7],
                        "timestamp": row[9]
                    })
                else:
                    safe_send(self, {"error": f"Transaction {tx_hash} not found"}, 404)
            
            # Адрес
            elif path.startswith("/api/address/"):
                address = path.split("/")[-1]
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM accounts WHERE address = ?", (address,))
                row = cursor.fetchone()
                
                # Получаем транзакции адреса
                cursor.execute("""
                    SELECT hash, block_number, from_addr, to_addr, value, timestamp 
                    FROM transactions 
                    WHERE from_addr = ? OR to_addr = ? 
                    ORDER BY block_number DESC LIMIT 20
                """, (address, address))
                txs = cursor.fetchall()
                conn.close()
                
                safe_send(self, {
                    "address": address,
                    "balance": row[1] if row else "0x0",
                    "tx_count": row[2] if row else 0,
                    "transactions": [
                        {"hash": tx[0], "block": tx[1], "from": tx[2], "to": tx[3], "value": tx[4], "timestamp": tx[5]}
                        for tx in txs
                    ]
                })
            
            # Поиск (как в Etherscan)
            elif path == "/api/search" and 'q' in query:
                q = query['q'][0].strip()
                conn = get_conn()
                cursor = conn.cursor()
                
                # По номеру блока
                if q.isdigit():
                    cursor.execute("SELECT * FROM blocks WHERE number = ?", (int(q),))
                    row = cursor.fetchone()
                    if row:
                        safe_send(self, {"type": "block", "data": {"number": row[0], "hash": row[1]}})
                        conn.close()
                        return
                
                # По хэшу транзакции
                if q.startswith("0x") and len(q) == 66:
                    cursor.execute("SELECT * FROM transactions WHERE hash = ?", (q,))
                    row = cursor.fetchone()
                    if row:
                        safe_send(self, {"type": "transaction", "data": {"hash": row[0], "block": row[1]}})
                        conn.close()
                        return
                
                # По адресу
                if q.startswith("0x") and len(q) == 42:
                    cursor.execute("SELECT * FROM accounts WHERE address = ?", (q,))
                    row = cursor.fetchone()
                    if row:
                        safe_send(self, {"type": "address", "data": {"address": row[0], "balance": row[1]}})
                        conn.close()
                        return
                
                conn.close()
                safe_send(self, {"type": "not_found", "query": q}, 404)
            
            # Список последних блоков
            elif path == "/api/blocks/latest":
                limit = int(query.get('limit', [10])[0])
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM blocks ORDER BY number DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                conn.close()
                
                safe_send(self, {
                    "blocks": [
                        {"number": row[0], "hash": row[1], "timestamp": row[3], "tx_count": row[4], "miner": row[5]}
                        for row in rows
                    ]
                })
            
            # Список последних транзакций
            elif path == "/api/txs/latest":
                limit = int(query.get('limit', [10])[0])
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM transactions ORDER BY block_number DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                conn.close()
                
                safe_send(self, {
                    "transactions": [
                        {"hash": row[0], "block": row[1], "from": row[2], "to": row[3], "value": row[4], "timestamp": row[9]}
                        for row in rows
                    ]
                })
            
            else:
                safe_send(self, {"error": "Not found"}, 404)
                
        except Exception as e:
            safe_send(self, {"error": str(e)}, 500)

if __name__ == "__main__":
    print("=" * 50)
    print("🌐 MAINNET API - Etherscan Compatible")
    print("=" * 50)
    print("📍 URL: http://localhost:8081")
    print("📡 Endpoints:")
    print("   GET /api/health")
    print("   GET /api/stats")
    print("   GET /api/block/latest")
    print("   GET /api/block/{number}")
    print("   GET /api/tx/{hash}")
    print("   GET /api/address/{address}")
    print("   GET /api/blocks/latest?limit=10")
    print("   GET /api/txs/latest?limit=10")
    print("   GET /api/search?q={query}")
    print("=" * 50)
    print("✅ API running! Press Ctrl+C to stop")
    print("=" * 50)
    
    server = HTTPServer(('0.0.0.0', 8081), MainnetAPIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 API stopped")
