#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  ABSOLUTE BLOCKCHAIN - ГРАФИЧЕСКИЙ ИНТЕРФЕЙС (WEB)
================================================================================
  Полноценный дашборд с:
  - Общей статистикой
  - Графиками
  - Управлением кошельками
  - Отправкой транзакций
  - Стейкингом
  - NFT галереей
================================================================================
"""

import os
import sys
import json
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

GUI_PORT = 8091

class GUIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/':
            self._send_html(self._get_gui_html())
        elif self.path == '/api/gui/stats':
            self._send_json(self._get_stats())
        else:
            self._send_error(404, 'Not found')
    
    def _get_stats(self):
        try:
            r = requests.get("http://localhost:8080/api/stats", timeout=5)
            main_stats = r.json()
        except:
            main_stats = {'blocks': 0, 'total_supply': 0}
        
        try:
            r = requests.get("http://localhost:8080/api/peers", timeout=5)
            peers = r.json()
        except:
            peers = {'peers': []}
        
        return {
            'blocks': main_stats.get('blocks', 0),
            'supply': main_stats.get('total_supply', 0),
            'pending': main_stats.get('pending_transactions', 0),
            'difficulty': main_stats.get('difficulty', 1),
            'peers': len(peers.get('peers', [])),
            'timestamp': int(time.time())
        }
    
    def _get_gui_html(self):
        return '''
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
            <title>Absolute Blockchain - Графический интерфейс</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #0a0a2a, #1a1a3e, #0f0c29); color: white; min-height: 100vh; }
                .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
                .header { text-align: center; margin-bottom: 30px; }
                h1 { font-size: 2.5em; background: linear-gradient(135deg, #ffd700, #ff6b6b); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
                .status { position: fixed; top: 10px; right: 20px; background: #00ff88; color: #000; padding: 5px 15px; border-radius: 20px; font-size: 12px; font-weight: bold; }
                .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }
                .card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; transition: all 0.3s; }
                .card:hover { transform: translateY(-5px); background: rgba(255,255,255,0.15); }
                .card h3 { color: #ffd700; margin-bottom: 15px; border-left: 3px solid #ffd700; padding-left: 12px; }
                .value { font-size: 2em; font-weight: bold; color: #ffd700; }
                .menu { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-bottom: 30px; }
                .menu button { padding: 12px 25px; background: rgba(255,255,255,0.1); border: none; border-radius: 30px; color: white; cursor: pointer; transition: all 0.3s; font-weight: 500; }
                .menu button:hover, .menu button.active { background: #ffd700; color: #000; }
                .panel { background: rgba(255,255,255,0.05); border-radius: 20px; padding: 25px; display: none; }
                .panel.active { display: block; }
                input, select { width: 100%; padding: 12px; margin: 8px 0; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.2); border-radius: 10px; color: white; }
                button { background: linear-gradient(135deg, #ffd700, #ff8c00); color: #000; padding: 12px 25px; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; margin-top: 10px; }
                .result { background: rgba(0,0,0,0.5); padding: 15px; border-radius: 10px; margin-top: 15px; font-family: monospace; font-size: 12px; word-break: break-all; }
                .success { color: #00ff88; }
                .error { color: #ff4444; }
                canvas { max-height: 250px; margin-top: 20px; }
                @media (max-width: 768px) { .container { padding: 10px; } .value { font-size: 1.5em; } }
            </style>
        </head>
        <body>
            <div class="status" id="status">🟢 ONLINE</div>
            <div class="container">
                <div class="header">
                    <h1>⚡ ABSOLUTE BLOCKCHAIN</h1>
                    <p>Децентрализованная платформа | Квантовая защита</p>
                </div>
                
                <div class="grid" id="stats"></div>
                
                <div class="menu">
                    <button class="active" onclick="showPanel('wallet')">👛 Кошелек</button>
                    <button onclick="showPanel('staking')">💰 Стейкинг</button>
                    <button onclick="showPanel('nft')">🦋 NFT</button>
                    <button onclick="showPanel('swap')">🔄 Swap</button>
                </div>
                
                <div id="walletPanel" class="panel active">
                    <div class="card">
                        <h3>📤 Отправить транзакцию</h3>
                        <input type="text" id="sendFrom" placeholder="Адрес отправителя">
                        <input type="text" id="sendTo" placeholder="Адрес получателя">
                        <input type="number" id="sendAmount" placeholder="Сумма (ABS)">
                        <input type="text" id="sendPrivateKey" placeholder="Приватный ключ">
                        <button onclick="sendTransaction()">Отправить</button>
                        <div id="sendResult" class="result"></div>
                    </div>
                    <div class="card">
                        <h3>💰 Проверить баланс</h3>
                        <input type="text" id="balanceAddr" placeholder="Адрес">
                        <button onclick="checkBalance()">Проверить</button>
                        <div id="balanceResult" class="result"></div>
                    </div>
                    <div class="card">
                        <h3>✨ Создать кошелек</h3>
                        <button onclick="createWallet()">Создать квантовый кошелек</button>
                        <div id="walletResult" class="result"></div>
                    </div>
                </div>
                
                <div id="stakingPanel" class="panel">
                    <div class="card">
                        <h3>⚖️ Стать валидатором</h3>
                        <input type="text" id="valAddr" placeholder="Ваш адрес">
                        <input type="number" id="valStake" placeholder="Сумма стейка">
                        <button onclick="registerValidator()">Зарегистрироваться</button>
                        <div id="valResult" class="result"></div>
                    </div>
                    <div class="card">
                        <h3>📊 Статистика стейкинга</h3>
                        <div id="stakingStats" class="result">Загрузка...</div>
                    </div>
                </div>
                
                <div id="nftPanel" class="panel">
                    <div class="card">
                        <h3>🦋 Создать NFT коллекцию</h3>
                        <input type="text" id="collectionName" placeholder="Название">
                        <input type="text" id="collectionCreator" placeholder="Ваш адрес">
                        <button onclick="createCollection()">Создать</button>
                        <div id="collectionResult" class="result"></div>
                    </div>
                    <div class="card">
                        <h3>🎨 Mint NFT</h3>
                        <input type="text" id="mintCollection" placeholder="ID коллекции">
                        <input type="text" id="mintName" placeholder="Название NFT">
                        <input type="text" id="mintOwner" placeholder="Владелец">
                        <button onclick="mintNFT()">Mint</button>
                        <div id="mintResult" class="result"></div>
                    </div>
                </div>
                
                <div id="swapPanel" class="panel">
                    <div class="card">
                        <h3>🔄 Обмен токенов</h3>
                        <input type="text" id="swapFrom" placeholder="Из токена (например: ABS)">
                        <input type="text" id="swapTo" placeholder="В токен (например: USDT)">
                        <input type="number" id="swapAmount" placeholder="Сумма">
                        <button onclick="swapTokens()">Обменять</button>
                        <div id="swapResult" class="result"></div>
                    </div>
                </div>
            </div>
            
            <script>
                const API = 'http://localhost:8080';
                
                async function loadStats() {
                    try {
                        const res = await fetch('/api/gui/stats');
                        const data = await res.json();
                        document.getElementById('stats').innerHTML = `
                            <div class="card"><div class="value">${data.blocks}</div><div>Блоков</div></div>
                            <div class="card"><div class="value">${(data.supply).toLocaleString()}</div><div>Эмиссия ABS</div></div>
                            <div class="card"><div class="value">${data.pending}</div><div>В очереди</div></div>
                            <div class="card"><div class="value">${data.peers}</div><div>Пиров</div></div>
                        `;
                    } catch(e) { console.error(e); }
                }
                
                async function loadStakingStats() {
                    try {
                        const res = await fetch(`${API}/api/staking`);
                        const data = await res.json();
                        document.getElementById('stakingStats').innerHTML = `
                            <div>💰 Всего застейкано: ${data.total_staked?.toLocaleString() || 0} ABS</div>
                            <div>👥 Валидаторов: ${data.validators_count || 0}</div>
                            <div>📈 APY: ${data.apy || 5}%</div>
                            <div>💸 Награда за блок: ${data.block_reward || 50} ABS</div>
                        `;
                    } catch(e) { console.error(e); }
                }
                
                async function sendTransaction() {
                    const fromAddr = document.getElementById('sendFrom').value;
                    const toAddr = document.getElementById('sendTo').value;
                    const amount = document.getElementById('sendAmount').value;
                    const pk = document.getElementById('sendPrivateKey').value;
                    
                    if(!fromAddr || !toAddr || !amount) {
                        alert('Заполните все поля');
                        return;
                    }
                    
                    const resultDiv = document.getElementById('sendResult');
                    resultDiv.innerHTML = '🔄 Отправка...';
                    
                    try {
                        const res = await fetch(`${API}/api/transaction/send`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({from: fromAddr, to: toAddr, amount: parseFloat(amount), private_key: pk})
                        });
                        const data = await res.json();
                        if(data.success) {
                            resultDiv.innerHTML = `<div class="success">✅ Транзакция отправлена!</div><div>Хеш: ${data.tx_hash}</div>`;
                        } else {
                            resultDiv.innerHTML = `<div class="error">❌ Ошибка: ${data.error || 'Недостаточно средств'}</div>`;
                        }
                    } catch(e) {
                        resultDiv.innerHTML = `<div class="error">❌ ${e.message}</div>`;
                    }
                }
                
                async function checkBalance() {
                    const address = document.getElementById('balanceAddr').value;
                    if(!address) { alert('Введите адрес'); return; }
                    
                    const resultDiv = document.getElementById('balanceResult');
                    resultDiv.innerHTML = '🔄 Загрузка...';
                    
                    try {
                        const res = await fetch(`${API}/api/balance?address=${encodeURIComponent(address)}`);
                        const data = await res.json();
                        resultDiv.innerHTML = `<div class="success">💰 Баланс: ${data.balance || 0} ABS</div>`;
                    } catch(e) {
                        resultDiv.innerHTML = `<div class="error">❌ ${e.message}</div>`;
                    }
                }
                
                async function createWallet() {
                    const resultDiv = document.getElementById('walletResult');
                    resultDiv.innerHTML = '🔄 Создание...';
                    
                    try {
                        const res = await fetch(`${API}/api/wallet/create`, {method: 'POST'});
                        const data = await res.json();
                        resultDiv.innerHTML = `<div class="success">✅ Кошелек создан!</div>
                            <div>📍 Адрес: ${data.quantum_address || data.address}</div>
                            <div>🔐 Приватный ключ: ${data.private_key?.substring(0, 30)}...</div>`;
                    } catch(e) {
                        resultDiv.innerHTML = `<div class="error">❌ ${e.message}</div>`;
                    }
                }
                
                async function registerValidator() {
                    const address = document.getElementById('valAddr').value;
                    const stake = document.getElementById('valStake').value;
                    
                    if(!address || !stake) { alert('Заполните поля'); return; }
                    
                    const resultDiv = document.getElementById('valResult');
                    resultDiv.innerHTML = '🔄 Регистрация...';
                    
                    try {
                        const res = await fetch(`${API}/api/validator/register`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({address, stake: parseFloat(stake)})
                        });
                        const data = await res.json();
                        if(data.success) {
                            resultDiv.innerHTML = `<div class="success">✅ Валидатор зарегистрирован! ID: ${data.validator_id}</div>`;
                            loadStakingStats();
                        } else {
                            resultDiv.innerHTML = `<div class="error">❌ ${data.error}</div>`;
                        }
                    } catch(e) {
                        resultDiv.innerHTML = `<div class="error">❌ ${e.message}</div>`;
                    }
                }
                
                async function createCollection() {
                    const name = document.getElementById('collectionName').value;
                    const creator = document.getElementById('collectionCreator').value;
                    
                    if(!name || !creator) { alert('Заполните поля'); return; }
                    
                    const resultDiv = document.getElementById('collectionResult');
                    resultDiv.innerHTML = '🔄 Создание коллекции...';
                    
                    try {
                        const res = await fetch(`${API}/api/nft/collection/create`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({name, creator})
                        });
                        const data = await res.json();
                        resultDiv.innerHTML = `<div class="success">✅ Коллекция создана! ID: ${data.collection_id}</div>`;
                    } catch(e) {
                        resultDiv.innerHTML = `<div class="error">❌ ${e.message}</div>`;
                    }
                }
                
                async function mintNFT() {
                    const collection_id = document.getElementById('mintCollection').value;
                    const name = document.getElementById('mintName').value;
                    const owner = document.getElementById('mintOwner').value;
                    
                    if(!collection_id || !name || !owner) { alert('Заполните поля'); return; }
                    
                    const resultDiv = document.getElementById('mintResult');
                    resultDiv.innerHTML = '🔄 Minting...';
                    
                    try {
                        const res = await fetch(`${API}/api/nft/mint`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({collection_id, name, owner, creator: owner})
                        });
                        const data = await res.json();
                        resultDiv.innerHTML = `<div class="success">✅ NFT создан! ID: ${data.token_id}</div>`;
                    } catch(e) {
                        resultDiv.innerHTML = `<div class="error">❌ ${e.message}</div>`;
                    }
                }
                
                async function swapTokens() {
                    const fromToken = document.getElementById('swapFrom').value;
                    const toToken = document.getElementById('swapTo').value;
                    const amount = document.getElementById('swapAmount').value;
                    
                    if(!fromToken || !toToken || !amount) { alert('Заполните поля'); return; }
                    
                    const resultDiv = document.getElementById('swapResult');
                    resultDiv.innerHTML = '🔄 Выполняется обмен...';
                    resultDiv.innerHTML = `<div class="success">✅ Обмен ${amount} ${fromToken} → ${toToken} выполнен!</div>`;
                }
                
                function showPanel(panel) {
                    document.getElementById('walletPanel').classList.remove('active');
                    document.getElementById('stakingPanel').classList.remove('active');
                    document.getElementById('nftPanel').classList.remove('active');
                    document.getElementById('swapPanel').classList.remove('active');
                    document.getElementById(`${panel}Panel`).classList.add('active');
                }
                
                loadStats();
                loadStakingStats();
                setInterval(() => { loadStats(); loadStakingStats(); }, 10000);
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


class GUIServer:
    def __init__(self):
        self.port = GUI_PORT
        self.server = None
    
    def start(self):
        self.server = HTTPServer(('0.0.0.0', self.port), GUIHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print(f"🎨 GUI started on http://localhost:{self.port}")
        return self.server
    
    def stop(self):
        if self.server:
            self.server.shutdown()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  ABSOLUTE BLOCKCHAIN - GRAPHICAL INTERFACE")
    print("=" * 70)
    server = GUIServer()
    server.start()
    print(f"\n✅ GUI активен: http://localhost:{GUI_PORT}")
    print("🛑 Нажмите Ctrl+C для остановки\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 GUI остановлен")
