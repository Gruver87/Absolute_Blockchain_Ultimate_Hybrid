#!/usr/bin/env python3
"""SIMPLE WEBSOCKET API - стабильная версия"""

import json
import sqlite3
import asyncio
import websockets
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DB_PATH = "blockchain.db"
WS_PORT = 8766

def get_conn():
    return sqlite3.connect(DB_PATH, timeout=30)

class SimpleAPI(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = self.path
        try:
            if path == '/api/health':
                self._send_json({"status": "ok", "ws_port": WS_PORT})
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
                self._send_json({"total_blocks": blocks, "total_transactions": txs, "total_addresses": addrs})
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

async def ws_handler(websocket):
    print("🔌 WebSocket client connected")
    try:
        # Отправляем приветствие
        await websocket.send(json.dumps({"type": "connected", "message": "Welcome to Absolute Blockchain"}))
        
        # Отправляем последние 10 блоков
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT number, hash, timestamp, tx_count, miner FROM blocks ORDER BY number DESC LIMIT 10")
        rows = c.fetchall()
        conn.close()
        
        blocks = [{"number": r[0], "hash": r[1][:16], "timestamp": r[2], "tx_count": r[3], "miner": r[4][:20]} for r in rows]
        await websocket.send(json.dumps({"type": "init", "blocks": blocks}))
        
        # Поддерживаем соединение
        while True:
            await asyncio.sleep(10)
            await websocket.send(json.dumps({"type": "ping"}))
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("🔌 WebSocket client disconnected")

async def start_ws():
    async with websockets.serve(ws_handler, "localhost", WS_PORT):
        print(f"🌐 WebSocket server on ws://localhost:{WS_PORT}")
        await asyncio.Future()

def run_ws():
    asyncio.run(start_ws())

def main():
    print("=" * 50)
    print("🌐 SIMPLE WEBSOCKET API v2")
    print("=" * 50)
    print(f"📍 HTTP API: http://localhost:8081")
    print(f"📍 WebSocket: ws://localhost:{WS_PORT}")
    print("=" * 50)
    
    # Запускаем WebSocket в потоке
    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()
    
    # Запускаем HTTP API
    server = ThreadingHTTPServer(('0.0.0.0', 8081), SimpleAPI)
    print("✅ HTTP API running")
    print("📍 http://localhost:8081/api/stats")
    print("📍 http://localhost:8081/api/blocks/latest?limit=10")
    print("=" * 50)
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")

if __name__ == "__main__":
    main()
