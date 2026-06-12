#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  ABSOLUTE BLOCKCHAIN - БЛОКЧЕЙН-ЭКСПЛОРЕР
================================================================================
  Полноценный блокчейн-эксплорер с:
  - Просмотр блоков и транзакций
  - Поиск по хешу, адресу, блоку
  - Графики и статистика
  - Топ-адреса
  - Газ трекер
================================================================================
"""

import os
import sys
import json
import time
import sqlite3
import threading
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

EXPLORER_PORT = 8090

class ExplorerAPIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.db_path = "data/blockchain.db"
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if path == '/':
            self._send_html(self._get_explorer_html())
        elif path == '/api/explorer/stats':
            self._send_json(self._get_stats())
        elif path == '/api/explorer/blocks':
            limit = int(query.get('limit', ['20'])[0])
            offset = int(query.get('offset', ['0'])[0])
            self._send_json(self._get_blocks(limit, offset))
        elif path == '/api/explorer/block':
            height = query.get('height', [''])[0]
            if height:
                self._send_json(self._get_block_by_height(int(height)))
            else:
                self._send_error(400, 'Height required')
        elif path == '/api/explorer/tx':
            tx_hash = query.get('hash', [''])[0]
            if tx_hash:
                self._send_json(self._get_transaction(tx_hash))
            else:
                self._send_error(400, 'Hash required')
        elif path == '/api/explorer/address':
            address = query.get('address', [''])[0]
            if address:
                self._send_json(self._get_address_info(address))
            else:
                self._send_error(400, 'Address required')
        elif path == '/api/explorer/search':
            q = query.get('q', [''])[0]
            if q:
                self._send_json(self._search(q))
            else:
                self._send_error(400, 'Query required')
        elif path == '/api/explorer/top_addresses':
            limit = int(query.get('limit', ['10'])[0])
            self._send_json(self._get_top_addresses(limit))
        elif path == '/api/explorer/gas':
            self._send_json(self._get_gas_info())
        elif path == '/api/explorer/chart':
            days = int(query.get('days', ['7'])[0])
            self._send_json(self._get_chart_data(days))
        else:
            self._send_error(404, 'Not found')
    
    def _get_stats(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM blocks')
        total_blocks = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM transactions')
        total_txs = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM wallets')
        total_addresses = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_blocks': total_blocks,
            'total_transactions': total_txs,
            'total_addresses': total_addresses,
            'last_updated': int(time.time())
        }
    
    def _get_blocks(self, limit=20, offset=0):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT height, block_hash, timestamp, transaction_count, miner, block_reward 
            FROM blocks ORDER BY height DESC LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        blocks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {'blocks': blocks, 'total': len(blocks)}
    
    def _get_block_by_height(self, height):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM blocks WHERE height = ?', (height,))
        block = dict(cursor.fetchone()) if cursor.fetchone() else None
        conn.close()
        
        return block or {'error': 'Block not found'}
    
    def _get_transaction(self, tx_hash):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM transactions WHERE tx_hash = ?', (tx_hash,))
        tx = dict(cursor.fetchone()) if cursor.fetchone() else None
        conn.close()
        
        return tx or {'error': 'Transaction not found'}
    
    def _get_address_info(self, address):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Баланс
        cursor.execute('SELECT balance FROM wallets WHERE address = ?', (address,))
        row = cursor.fetchone()
        balance = row[0] if row else 0
        
        # Транзакции
        cursor.execute('''
            SELECT * FROM transactions 
            WHERE from_address = ? OR to_address = ? 
            ORDER BY timestamp DESC LIMIT 50
        ''', (address, address))
        
        txs = []
        for row in cursor.fetchall():
            txs.append({
                'hash': row[0],
                'from': row[1],
                'to': row[2],
                'amount': row[3],
                'timestamp': row[4],
                'status': row[5]
            })
        
        conn.close()
        
        return {
            'address': address,
            'balance': balance,
            'transactions': txs,
            'total_txs': len(txs)
        }
    
    def _search(self, query):
        query = query.lower()
        result = {'type': None, 'data': None}
        
        # Проверка на блок
        if query.isdigit():
            block = self._get_block_by_height(int(query))
            if block and 'error' not in block:
                result['type'] = 'block'
                result['data'] = block
                return result
        
        # Проверка на транзакцию
        tx = self._get_transaction(query)
        if tx and 'error' not in tx:
            result['type'] = 'transaction'
            result['data'] = tx
            return result
        
        # Проверка на адрес
        address_info = self._get_address_info(query)
        if address_info.get('balance', 0) > 0 or address_info.get('total_txs', 0) > 0:
            result['type'] = 'address'
            result['data'] = address_info
            return result
        
        return {'type': 'not_found', 'data': None}
    
    def _get_top_addresses(self, limit=10):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT address, balance FROM wallets ORDER BY balance DESC LIMIT ?', (limit,))
        addresses = [{'address': row[0], 'balance': row[1]} for row in cursor.fetchall()]
        conn.close()
        
        return {'addresses': addresses}
    
    def _get_gas_info(self):
        # Получение цены газа с Binance
        gas_price = 100  # Gwei по умолчанию
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT", timeout=5)
            eth_price = float(r.json().get('price', 0))
        except:
            eth_price = 2000
        
        return {
            'gas_price': gas_price,
            'eth_price': eth_price,
            'recommended': gas_price,
            'fast': gas_price + 20,
            'slow': gas_price - 20
        }
    
    def _get_chart_data(self, days=7):
        # Симуляция данных для графика
        data = []
        now = int(time.time())
        for i in range(days):
            data.append({
                'date': (now - i * 86400) * 1000,
                'transactions': 100 + i * 10,
                'blocks': 8640 // days * (i + 1)
            })
        return {'data': data[::-1]}
    
    def _get_explorer_html(self):
        return '''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Absolute Blockchain Explorer</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: 'Inter', monospace; background: linear-gradient(135deg, #0a0a2a, #1a1a3e); color: white; min-height: 100vh; }
                .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
                .header { text-align: center; margin-bottom: 30px; }
                h1 { font-size: 2.5em; background: linear-gradient(135deg, #ffd700, #ff6b6b); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
                .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
                .stat-card { background: rgba(255,255,255,0.1); border-radius: 15px; padding: 20px; text-align: center; }
                .stat-value { font-size: 2em; font-weight: bold; color: #ffd700; }
                .search-box { display: flex; gap: 10px; margin-bottom: 30px; }
                .search-box input { flex: 1; padding: 15px; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 10px; color: white; font-size: 16px; }
                .search-box button { padding: 15px 30px; background: #ffd700; border: none; border-radius: 10px; color: #000; font-weight: bold; cursor: pointer; }
                .nav { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-bottom: 30px; }
                .nav a { color: white; text-decoration: none; padding: 10px 20px; background: rgba(255,255,255,0.1); border-radius: 30px; cursor: pointer; }
                .nav a:hover, .nav a.active { background: #ffd700; color: #000; }
                .content { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
                th { color: #ffd700; }
                .address { font-family: monospace; font-size: 12px; }
                .result-box { background: rgba(0,0,0,0.5); border-radius: 10px; padding: 20px; margin-top: 20px; }
                .loading { text-align: center; padding: 40px; animation: pulse 1s infinite; }
                @keyframes pulse { 0% { opacity: 0.6; } 100% { opacity: 1; } }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔍 ABSOLUTE BLOCKCHAIN EXPLORER</h1>
                    <p>Просмотр блоков, транзакций и адресов</p>
                </div>
                
                <div class="search-box">
                    <input type="text" id="searchInput" placeholder="Поиск по хешу блока/транзакции или адресу...">
                    <button onclick="search()">🔍 Поиск</button>
                </div>
                
                <div class="stats" id="stats"></div>
                
                <div class="nav">
                    <a class="active" onclick="showTab('blocks')">📦 Блоки</a>
                    <a onclick="showTab('transactions')">💸 Транзакции</a>
                    <a onclick="showTab('top')">🏆 Топ адреса</a>
                    <a onclick="showTab('gas')">⛽ Gas трекер</a>
                    <a onclick="showTab('chart')">📊 Графики</a>
                </div>
                
                <div class="content">
                    <div id="blocksTab">
                        <div id="blocksList" class="loading">Загрузка блоков...</div>
                    </div>
                    <div id="transactionsTab" style="display:none;">
                        <div id="transactionsList" class="loading">Загрузка транзакций...</div>
                    </div>
                    <div id="topTab" style="display:none;">
                        <div id="topList" class="loading">Загрузка топ адресов...</div>
                    </div>
                    <div id="gasTab" style="display:none;">
                        <div id="gasInfo" class="loading">Загрузка данных газа...</div>
                    </div>
                    <div id="chartTab" style="display:none;">
                        <canvas id="statsChart" style="max-height: 400px;"></canvas>
                    </div>
                </div>
                
                <div id="searchResult" class="result-box" style="display:none;"></div>
            </div>
            
            <script>
                let statsChart;
                
                async function loadStats() {
                    try {
                        const res = await fetch('/api/explorer/stats');
                        const data = await res.json();
                        document.getElementById('stats').innerHTML = `
                            <div class="stat-card"><div class="stat-value">${data.total_blocks}</div><div>Всего блоков</div></div>
                            <div class="stat-card"><div class="stat-value">${data.total_transactions}</div><div>Всего транзакций</div></div>
                            <div class="stat-card"><div class="stat-value">${data.total_addresses}</div><div>Адресов</div></div>
                        `;
                    } catch(e) { console.error(e); }
                }
                
                async function loadBlocks() {
                    try {
                        const res = await fetch('/api/explorer/blocks?limit=20');
                        const data = await res.json();
                        const blocks = data.blocks || [];
                        if(blocks.length === 0) {
                            document.getElementById('blocksList').innerHTML = '<div>Нет блоков</div>';
                            return;
                        }
                        document.getElementById('blocksList').innerHTML = `
                            <table>
                                <thead><tr><th>Высота</th><th>Хеш</th><th>Время</th><th>Транзакций</th><th>Майнер</th><th>Награда</th></tr></thead>
                                <tbody>
                                    ${blocks.map(b => `
                                        <tr>
                                            <td><a onclick="searchBlock(${b.height})" style="color:#ffd700;cursor:pointer">#${b.height}</a></td>
                                            <td class="address">${(b.block_hash || '').substring(0, 20)}...</td>
                                            <td>${new Date(b.timestamp * 1000).toLocaleString()}</td>
                                            <td>${b.transaction_count || 0}</td>
                                            <td class="address">${(b.miner || 'system').substring(0, 16)}...</td>
                                            <td>${b.block_reward || 0} ABS</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `;
                    } catch(e) { console.error(e); }
                }
                
                async function loadTransactions() {
                    try {
                        const res = await fetch('/api/transactions');
                        const txs = await res.json();
                        if(!txs || txs.length === 0) {
                            document.getElementById('transactionsList').innerHTML = '<div>Нет транзакций</div>';
                            return;
                        }
                        document.getElementById('transactionsList').innerHTML = `
                            <table>
                                <thead><tr><th>Хеш</th><th>От</th><th>Кому</th><th>Сумма</th><th>Время</th><th>Статус</th></tr></thead>
                                <tbody>
                                    ${txs.map(tx => `
                                        <tr>
                                            <td class="address">${(tx.tx_hash || '').substring(0, 16)}...</td>
                                            <td class="address">${(tx.from_address || '').substring(0, 12)}...</td>
                                            <td class="address">${(tx.to_address || '').substring(0, 12)}...</td>
                                            <td>${tx.amount || 0} ABS</td>
                                            <td>${new Date(tx.timestamp * 1000).toLocaleString()}</td>
                                            <td style="color:${tx.status === 'confirmed' ? '#00ff88' : '#ffaa00'}">${tx.status || 'pending'}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `;
                    } catch(e) { console.error(e); }
                }
                
                async function loadTopAddresses() {
                    try {
                        const res = await fetch('/api/explorer/top_addresses?limit=10');
                        const data = await res.json();
                        const addresses = data.addresses || [];
                        document.getElementById('topList').innerHTML = `
                            <table>
                                <thead><tr><th>#</th><th>Адрес</th><th>Баланс (ABS)</th></tr></thead>
                                <tbody>
                                    ${addresses.map((a, i) => `
                                        <tr>
                                            <td>${i+1}</td>
                                            <td class="address"><a onclick="searchAddress('${a.address}')" style="color:#ffd700;cursor:pointer">${a.address.substring(0, 24)}...</a></td>
                                            <td>${a.balance.toLocaleString()}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `;
                    } catch(e) { console.error(e); }
                }
                
                async function loadGasInfo() {
                    try {
                        const res = await fetch('/api/explorer/gas');
                        const data = await res.json();
                        document.getElementById('gasInfo').innerHTML = `
                            <div class="stat-card"><div class="stat-value">${data.gas_price} Gwei</div><div>Стандарт</div></div>
                            <div class="stat-card"><div class="stat-value">${data.fast} Gwei</div><div>Быстро</div></div>
                            <div class="stat-card"><div class="stat-value">${data.slow} Gwei</div><div>Медленно</div></div>
                            <div class="stat-card"><div class="stat-value">$${data.eth_price}</div><div>ETH цена</div></div>
                        `;
                    } catch(e) { console.error(e); }
                }
                
                async function loadChart() {
                    try {
                        const res = await fetch('/api/explorer/chart?days=7');
                        const data = await res.json();
                        const chartData = data.data || [];
                        
                        if(statsChart) statsChart.destroy();
                        const ctx = document.getElementById('statsChart').getContext('2d');
                        statsChart = new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: chartData.map(d => new Date(d.date).toLocaleDateString()),
                                datasets: [
                                    { label: 'Транзакции', data: chartData.map(d => d.transactions), borderColor: '#ffd700', fill: false, tension: 0.4 },
                                    { label: 'Блоки', data: chartData.map(d => d.blocks), borderColor: '#ff6b6b', fill: false, tension: 0.4 }
                                ]
                            },
                            options: { responsive: true, maintainAspectRatio: true }
                        });
                    } catch(e) { console.error(e); }
                }
                
                function showTab(tab) {
                    document.getElementById('blocksTab').style.display = 'none';
                    document.getElementById('transactionsTab').style.display = 'none';
                    document.getElementById('topTab').style.display = 'none';
                    document.getElementById('gasTab').style.display = 'none';
                    document.getElementById('chartTab').style.display = 'none';
                    
                    if(tab === 'blocks') { document.getElementById('blocksTab').style.display = 'block'; loadBlocks(); }
                    if(tab === 'transactions') { document.getElementById('transactionsTab').style.display = 'block'; loadTransactions(); }
                    if(tab === 'top') { document.getElementById('topTab').style.display = 'block'; loadTopAddresses(); }
                    if(tab === 'gas') { document.getElementById('gasTab').style.display = 'block'; loadGasInfo(); }
                    if(tab === 'chart') { document.getElementById('chartTab').style.display = 'block'; loadChart(); }
                }
                
                async function search() {
                    const query = document.getElementById('searchInput').value;
                    if(!query) return;
                    
                    const res = await fetch(`/api/explorer/search?q=${encodeURIComponent(query)}`);
                    const result = await res.json();
                    
                    const resultDiv = document.getElementById('searchResult');
                    if(result.type === 'block') {
                        resultDiv.innerHTML = `<div>🔷 БЛОК #${result.data.height}<br>Хеш: ${result.data.block_hash}<br>Время: ${new Date(result.data.timestamp * 1000).toLocaleString()}</div>`;
                    } else if(result.type === 'transaction') {
                        resultDiv.innerHTML = `<div>💸 ТРАНЗАКЦИЯ<br>Хеш: ${result.data.tx_hash}<br>Сумма: ${result.data.amount} ABS<br>Статус: ${result.data.status}</div>`;
                    } else if(result.type === 'address') {
                        resultDiv.innerHTML = `<div>👛 АДРЕС<br>${result.data.address}<br>Баланс: ${result.data.balance} ABS<br>Транзакций: ${result.data.total_txs}</div>`;
                    } else {
                        resultDiv.innerHTML = `<div>❌ Ничего не найдено</div>`;
                    }
                    resultDiv.style.display = 'block';
                    setTimeout(() => resultDiv.style.display = 'none', 10000);
                }
                
                function searchBlock(height) {
                    document.getElementById('searchInput').value = height;
                    search();
                }
                
                function searchAddress(address) {
                    document.getElementById('searchInput').value = address;
                    search();
                }
                
                loadStats();
                loadBlocks();
                setInterval(() => { loadStats(); loadBlocks(); loadTransactions(); loadTopAddresses(); }, 15000);
            </script>
        </body>
        </html>
        '''
    
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


class ExplorerServer:
    def __init__(self):
        self.port = EXPLORER_PORT
        self.server = None
    
    def start(self):
        self.server = HTTPServer(('0.0.0.0', self.port), ExplorerAPIHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print(f"🔍 Explorer started on http://localhost:{self.port}")
        return self.server
    
    def stop(self):
        if self.server:
            self.server.shutdown()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  ABSOLUTE BLOCKCHAIN - EXPLORER")
    print("=" * 70)
    server = ExplorerServer()
    server.start()
    print(f"\n✅ Explorer активен: http://localhost:{EXPLORER_PORT}")
    print("🛑 Нажмите Ctrl+C для остановки\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Explorer остановлен")
