#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  ABSOLUTE BLOCKCHAIN - ТЕСТОВАЯ СЕТЬ (TESTNET) FIXED
================================================================================
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Optional, Any

# ============== КОНФИГ ТЕСТОВОЙ СЕТИ ==============

class TestnetConfig:
    PORT = 8088
    P2P_PORT = 6000
    BLOCK_TIME = 5
    BLOCK_REWARD = 10.0
    FAUCET_AMOUNT = 1000
    FAUCET_COOLDOWN = 60
    INITIAL_SUPPLY = 10_000_000

# ============== БАЗА ДАННЫХ ТЕСТНЕТА ==============

class TestnetDB:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self.db_path = "data/testnet.db"
        self._init_db()
        print("✅ Testnet database initialized")
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS testnet_blocks (
                height INTEGER PRIMARY KEY,
                block_hash TEXT UNIQUE,
                previous_hash TEXT,
                timestamp INTEGER,
                transactions TEXT,
                miner TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS testnet_transactions (
                tx_hash TEXT PRIMARY KEY,
                from_addr TEXT,
                to_addr TEXT,
                amount REAL,
                timestamp INTEGER,
                status TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS testnet_wallets (
                address TEXT PRIMARY KEY,
                balance REAL DEFAULT 0,
                faucet_last_claim INTEGER DEFAULT 0
            )
        ''')
        
        initial_wallets = [
            ('testnet_faucet', TestnetConfig.FAUCET_AMOUNT * 1000),
            ('testnet_validator1', 100000),
            ('testnet_validator2', 100000),
            ('testnet_user1', 10000),
            ('testnet_user2', 10000),
            ('testnet_user3', 10000)
        ]
        
        for addr, bal in initial_wallets:
            cursor.execute('INSERT OR IGNORE INTO testnet_wallets (address, balance) VALUES (?, ?)', (addr, bal))
        
        cursor.execute('SELECT COUNT(*) FROM testnet_blocks')
        if cursor.fetchone()[0] == 0:
            genesis = {
                'height': 0,
                'block_hash': hashlib.sha256(b'genesis_testnet').hexdigest(),
                'previous_hash': '0'*64,
                'timestamp': int(time.time()),
                'transactions': json.dumps([]),
                'miner': 'system'
            }
            cursor.execute('''
                INSERT INTO testnet_blocks (height, block_hash, previous_hash, timestamp, transactions, miner)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (0, genesis['block_hash'], genesis['previous_hash'], genesis['timestamp'], genesis['transactions'], genesis['miner']))
        
        conn.commit()
        conn.close()

# ============== FAUCET ==============

class TestnetFaucet:
    def __init__(self, db: TestnetDB):
        self.db = db
    
    def claim(self, address: str) -> Dict:
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT faucet_last_claim, balance FROM testnet_wallets WHERE address = ?', (address,))
        row = cursor.fetchone()
        
        if not row:
            cursor.execute('INSERT INTO testnet_wallets (address, balance, faucet_last_claim) VALUES (?, ?, ?)',
                          (address, 0, 0))
            last_claim = 0
            balance = 0
        else:
            last_claim = row[0] or 0
            balance = row[1] or 0
        
        current_time = int(time.time())
        if current_time - last_claim < TestnetConfig.FAUCET_COOLDOWN:
            wait_time = TestnetConfig.FAUCET_COOLDOWN - (current_time - last_claim)
            conn.close()
            return {'success': False, 'error': f'Please wait {wait_time} seconds', 'wait_time': wait_time}
        
        new_balance = balance + TestnetConfig.FAUCET_AMOUNT
        cursor.execute('UPDATE testnet_wallets SET balance = ?, faucet_last_claim = ? WHERE address = ?',
                      (new_balance, current_time, address))
        
        tx_hash = hashlib.sha256(f"faucet_{address}_{current_time}".encode()).hexdigest()
        cursor.execute('''
            INSERT INTO testnet_transactions (tx_hash, from_addr, to_addr, amount, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (tx_hash, 'testnet_faucet', address, TestnetConfig.FAUCET_AMOUNT, current_time, 'confirmed'))
        
        conn.commit()
        conn.close()
        
        print(f"💰 Faucet: {TestnetConfig.FAUCET_AMOUNT} tABS to {address[:16]}...")
        return {
            'success': True,
            'amount': TestnetConfig.FAUCET_AMOUNT,
            'new_balance': new_balance,
            'tx_hash': tx_hash
        }
    
    def get_balance(self, address: str) -> float:
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM testnet_wallets WHERE address = ?', (address,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0

# ============== API ==============

class TestnetAPIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.db = TestnetDB()
        self.faucet = TestnetFaucet(self.db)
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if path == '/':
            self._send_html(self._get_testnet_page())
        elif path == '/api/testnet/stats':
            self._send_json(self._get_stats())
        elif path == '/api/testnet/balance':
            address = query.get('address', [''])[0]
            if address:
                balance = self.faucet.get_balance(address)
                self._send_json({'address': address, 'balance': balance})
            else:
                self._send_error(400, 'Address required')
        elif path == '/api/testnet/faucet/info':
            self._send_json({
                'amount': TestnetConfig.FAUCET_AMOUNT,
                'cooldown': TestnetConfig.FAUCET_COOLDOWN,
                'total_supply': TestnetConfig.INITIAL_SUPPLY
            })
        elif path == '/api/testnet/transactions':
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM testnet_transactions ORDER BY timestamp DESC LIMIT 20')
            txs = [{'tx_hash': row[0], 'from': row[1], 'to': row[2], 'amount': row[3], 'timestamp': row[4], 'status': row[5]} for row in cursor.fetchall()]
            conn.close()
            self._send_json({'transactions': txs})
        else:
            self._send_error(404, 'Not found')
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b'{}'
        
        try:
            data = json.loads(body.decode('utf-8'))
        except:
            data = {}
        
        path = self.path
        
        if path == '/api/testnet/faucet/claim':
            address = data.get('address')
            if not address:
                self._send_json({'success': False, 'error': 'Address required'})
                return
            result = self.faucet.claim(address)
            self._send_json(result)
        else:
            self._send_error(404, 'Not found')
    
    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
    
    def _send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def _send_error(self, code, message):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}).encode())
    
    def _get_stats(self):
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM testnet_wallets')
        wallets_count = cursor.fetchone()[0]
        cursor.execute('SELECT SUM(amount) FROM testnet_transactions WHERE from_addr = "testnet_faucet"')
        faucet_total = cursor.fetchone()[0] or 0
        cursor.execute('SELECT COUNT(*) FROM testnet_transactions')
        txs_count = cursor.fetchone()[0]
        conn.close()
        
        return {
            'total_supply': TestnetConfig.INITIAL_SUPPLY,
            'faucet_claimed': faucet_total,
            'wallets_count': wallets_count,
            'transactions_count': txs_count,
            'faucet_amount': TestnetConfig.FAUCET_AMOUNT,
            'faucet_cooldown': TestnetConfig.FAUCET_COOLDOWN
        }
    
    def _get_testnet_page(self):
        return '''
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"><title>Absolute Testnet</title>
        <style>
            body{font-family:monospace;background:linear-gradient(135deg,#0a0a2a,#1a1a3e);color:white;padding:20px}
            .container{max-width:800px;margin:0 auto}
            .card{background:rgba(255,255,255,0.1);border-radius:15px;padding:20px;margin:20px 0}
            button{background:#ffd700;color:#000;padding:10px 20px;border:none;border-radius:8px;cursor:pointer}
            input{padding:10px;margin:5px;background:rgba(0,0,0,0.5);color:white;border:none;border-radius:8px;width:250px}
            .result{background:rgba(0,0,0,0.5);padding:15px;border-radius:10px;margin-top:15px}
            .success{color:#00ff88}
        </style>
        </head>
        <body>
        <div class="container">
            <h1>🧪 Absolute Blockchain Testnet</h1>
            <div class="card">
                <h2>💰 Faucet</h2>
                <input type="text" id="address" placeholder="Ваш адрес">
                <button onclick="claim()">Получить tABS</button>
                <div id="result" class="result"></div>
            </div>
            <div class="card">
                <h2>🔍 Проверить баланс</h2>
                <input type="text" id="balanceAddr" placeholder="Адрес">
                <button onclick="checkBalance()">Проверить</button>
                <div id="balanceResult" class="result"></div>
            </div>
        </div>
        <script>
        async function claim(){
            const addr=document.getElementById('address').value;
            if(!addr){alert('Введите адрес');return;}
            const res=await fetch('/api/testnet/faucet/claim',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address:addr})});
            const d=await res.json();
            const div=document.getElementById('result');
            if(d.success){div.innerHTML=`<div class="success">✅ Получено ${d.amount} tABS!</div><div>💰 Новый баланс: ${d.new_balance} tABS</div>`;}
            else{div.innerHTML=`<div class="error">❌ ${d.error}</div>`;}
        }
        async function checkBalance(){
            const addr=document.getElementById('balanceAddr').value;
            if(!addr){alert('Введите адрес');return;}
            const res=await fetch(`/api/testnet/balance?address=${encodeURIComponent(addr)}`);
            const d=await res.json();
            document.getElementById('balanceResult').innerHTML=`💰 Баланс: ${d.balance} tABS`;
        }
        </script>
        </body>
        </html>
        '''


class TestnetServer:
    def __init__(self):
        self.port = TestnetConfig.PORT
        self.server = None
    
    def start(self):
        self.server = HTTPServer(('0.0.0.0', self.port), TestnetAPIHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print(f"🧪 Testnet Server started on http://localhost:{self.port}")
        print(f"💰 Faucet: http://localhost:{self.port}")
        return self.server


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  ABSOLUTE BLOCKCHAIN - TESTNET (FIXED)")
    print("="*60)
    
    server = TestnetServer()
    server.start()
    
    print(f"\n✅ Testnet активен на порту {TestnetConfig.PORT}")
    print(f"💰 Faucet выдает {TestnetConfig.FAUCET_AMOUNT} tABS каждые {TestnetConfig.FAUCET_COOLDOWN} секунд")
    print("\n🛑 Нажмите Ctrl+C для остановки\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Testnet остановлен")
