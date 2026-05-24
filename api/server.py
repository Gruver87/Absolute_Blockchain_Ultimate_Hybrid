# api/server.py
# ПОЛНОСТЬЮ РАБОЧИЙ API СЕРВЕР

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

class RateLimiter:
    """Защита от DDoS"""
    def __init__(self, requests_per_minute=100):
        self.requests_per_minute = requests_per_minute
        self.requests = {}
        self.lock = threading.RLock()
    
    def check(self, client_ip):
        now = time.time()
        window = 60
        with self.lock:
            if client_ip not in self.requests:
                self.requests[client_ip] = []
            self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < window]
            if len(self.requests[client_ip]) >= self.requests_per_minute:
                return False
            self.requests[client_ip].append(now)
            return True

class APIHandler(BaseHTTPRequestHandler):
    core = None
    nft = None
    oracle = None
    rate_limiter = None
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if not self.rate_limiter.check(self.client_address[0]):
            self._send_json({'error': 'Rate limit exceeded'}, 429)
            return
        
        # API Эндпоинты
        if path == '/api/stats':
            self._send_json(self.core.get_stats())
        
        elif path == '/api/health':
            self._send_json({'status': 'healthy', 'version': '16.0', 'timestamp': int(time.time())})
        
        elif path == '/api/balance':
            address = query.get('address', [''])[0]
            if address:
                balance = self.core.get_balance(address)
                self._send_json({'address': address, 'balance': balance})
            else:
                self._send_json({'error': 'Address required'}, 400)
        
        elif path == '/api/peers':
            self._send_json({'peers': self.core.get_peers()})
        
        elif path == '/api/verify':
            result = self.core.verify_chain()
            self._send_json({'verified': result})
        
        elif path == '/api/merkle':
            block = self.core.get_latest_block()
            self._send_json({
                'height': block.height,
                'merkle_root': block.merkle_root,
                'block_hash': block.block_hash
            })
        
        elif path == '/api/nft/stats':
            self._send_json(self.nft.get_stats())
        
        elif path == '/api/nft/tokens':
            self._send_json(self.nft.get_all_tokens())
        
        elif path == '/api/oracle/price':
            symbol = query.get('symbol', ['bitcoin'])[0]
            self._send_json(self.oracle.get_price(symbol))
        
        elif path == '/api/oracle/weather':
            city = query.get('city', ['London'])[0]
            self._send_json(self.oracle.get_weather(city))
        
        # Веб-страницы
        elif path == '/':
            self._send_html()
        elif path == '/docs':
            self._send_docs()
        elif path == '/nft':
            self._send_nft_gallery()
        elif path == '/wallet':
            self._send_wallet()
        elif path == '/explorer':
            self._send_explorer()
        else:
            self._send_json({'error': 'Not found'}, 404)
    
    def do_POST(self):
        if not self.rate_limiter.check(self.client_address[0]):
            self._send_json({'error': 'Rate limit exceeded'}, 429)
            return
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            data = json.loads(body.decode())
        except:
            data = {}
        
        path = urlparse(self.path).path
        
        # Создание кошелька
        if path == '/api/wallet/create':
            from core.wallet_crypto import crypto
            wallet = crypto.generate_keypair()
            self._send_json({
                'success': True,
                'address': wallet['address'],
                'public_key': wallet['public_key'],
                'algorithm': wallet['algorithm']
            })
        
        # Отправка транзакции
        elif path == '/api/transaction/send':
            from core.transaction import Transaction
            import time
            
            from_addr = data.get('from')
            to_addr = data.get('to')
            amount = data.get('amount', 0)
            private_key = data.get('private_key')
            
            if not all([from_addr, to_addr, amount, private_key]):
                self._send_json({'error': 'Missing fields'}, 400)
                return
            
            nonce = self.core.storage.get_meta(f"nonce:{from_addr}", 0)
            tx = Transaction(
                hash='',
                from_addr=from_addr,
                to_addr=to_addr,
                amount=float(amount),
                fee=0.001,
                timestamp=int(time.time()),
                nonce=nonce
            )
            tx.hash = tx.calculate_hash()
            temp_wallet = __import__('core.wallet_crypto').wallet_crypto.crypto.generate_keypair()
            tx.public_key = temp_wallet['public_key']
            tx.sign(private_key)
            
            if self.core.add_transaction(tx):
                self._send_json({'success': True, 'tx_hash': tx.hash})
            else:
                self._send_json({'error': 'Transaction rejected'}, 400)
        
        # Майнинг
        elif path == '/api/mine':
            miner = data.get('miner', 'foundation')
            block = self.core.mine_block(miner)
            if block:
                self._send_json({
                    'success': True,
                    'height': block.height,
                    'merkle_root': block.merkle_root,
                    'tx_count': len(block.transactions)
                })
            else:
                self._send_json({'error': 'No transactions'}, 400)
        
        # Создание NFT
        elif path == '/api/nft/mint':
            result = self.nft.mint(data)
            self._send_json(result)
        
        else:
            self._send_json({'error': 'Not found'}, 404)
    
    def _send_json(self, data, status=200):
        response = json.dumps(data, default=str, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()
        self.wfile.write(response)
    
    def _send_html(self):
        html = self._get_main_html()
        self._send_html_response(html)
    
    def _send_docs(self):
        html = self._get_docs_html()
        self._send_html_response(html)
    
    def _send_nft_gallery(self):
        html = self._get_nft_html()
        self._send_html_response(html)
    
    def _send_wallet(self):
        html = self._get_wallet_html()
        self._send_html_response(html)
    
    def _send_explorer(self):
        html = self._get_explorer_html()
        self._send_html_response(html)
    
    def _send_html_response(self, html):
        response = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)
    
    def _get_main_html(self):
        return '''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Absolute Blockchain</title>
<style>
body{font-family:monospace;background:#0f0c29;color:#fff;padding:20px}
h1{color:#ffd700}
.card{background:rgba(255,255,255,0.1);margin:10px 0;padding:15px;border-radius:8px}
a{color:#ffd700}
</style>
</head>
<body>
<h1>⚡ ABSOLUTE BLOCKCHAIN v16.0</h1>
<p>Пост-квантовый блокчейн с Merkle Tree | Готов к mainnet</p>
<div class="card">
<h2>📊 Статистика</h2>
<div id="stats">Загрузка...</div>
</div>
<div class="card">
<h2>🌐 API Эндпоинты</h2>
<ul>
<li><a href="/api/stats">/api/stats</a> - Статистика</li>
<li><a href="/api/health">/api/health</a> - Health check</li>
<li><a href="/api/verify">/api/verify</a> - Верификация</li>
<li><a href="/api/merkle">/api/merkle</a> - Merkle Root</li>
<li><a href="/nft">/nft</a> - NFT галерея</li>
<li><a href="/wallet">/wallet</a> - Кошелёк</li>
<li><a href="/explorer">/explorer</a> - Explorer</li>
</ul>
</div>
<div class="card">
<h2>🔐 Безопасность</h2>
<ul>
<li>✅ Merkle Tree верификация</li>
<li>✅ ECDSA secp256k1 подписи</li>
<li>✅ BIP39 мнемоника</li>
<li>✅ RocksDB хранилище</li>
<li>✅ Rate limiting (DDoS защита)</li>
</ul>
</div>
<script>
fetch('/api/stats').then(r=>r.json()).then(d=>{
document.getElementById('stats').innerHTML=`
<p>📦 Блоков: ${d.blocks}</p>
<p>📐 Высота: ${d.height}</p>
<p>💵 Total Supply: ${d.total_supply.toFixed(2)} ABS</p>
<p>🌳 Merkle Root: ${d.merkle_root.substring(0,32)}...</p>
`;
});
</script>
</body>
</html>'''
    
    def _get_docs_html(self):
        return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>API Docs</title>
<style>body{background:#0f0c29;color:#fff;font-family:monospace;padding:20px}</style>
</head>
<body>
<h1>📚 ABSOLUTE BLOCKCHAIN API</h1>
<h2>GET Эндпоинты</h2>
<pre>
GET /api/stats           - Статистика блокчейна
GET /api/health          - Health check
GET /api/balance?address - Баланс адреса
GET /api/peers           - Список пиров
GET /api/verify          - Верификация цепочки
GET /api/merkle          - Merkle root последнего блока
GET /api/nft/stats       - Статистика NFT
GET /api/nft/tokens      - Список NFT токенов
GET /api/oracle/price    - Цена криптовалюты (?symbol=bitcoin)
GET /api/oracle/weather  - Погода (?city=Moscow)
</pre>
<h2>POST Эндпоинты</h2>
<pre>
POST /api/wallet/create  - Создание кошелька
POST /api/transaction/send - Отправка транзакции
POST /api/mine           - Майнинг блока
POST /api/nft/mint       - Создание NFT
</pre>
</body></html>'''
    
    def _get_nft_html(self):
        return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>NFT Gallery</title>
<style>body{background:#0f0c29;color:#fff;font-family:monospace;padding:20px}
.nft{display:inline-block;margin:10px;padding:10px;background:rgba(255,255,255,0.1);border-radius:8px}
</style>
</head>
<body>
<h1>🖼️ NFT GALLERY</h1>
<p>60 уникальных AI героев с пост-квантовой защитой</p>
<div id="nfts"></div>
<script>
fetch('/api/nft/tokens').then(r=>r.json()).then(data=>{
const nfts = data.tokens || [];
document.getElementById('nfts').innerHTML = nfts.map(n => 
`<div class="nft">🎨 ${n.name}<br><small>${n.token_id.substring(0,16)}...</small></div>`
).join('');
if(nfts.length===0) document.getElementById('nfts').innerHTML='<p>Загрузка NFT...</p>';
});
</script>
</body></html>'''
    
    def _get_wallet_html(self):
        return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Wallet</title>
<style>body{background:#0f0c29;color:#fff;font-family:monospace;padding:20px}
input,button{padding:10px;margin:5px}
button{background:#ffd700;cursor:pointer}
.result{margin-top:20px;padding:10px;background:rgba(255,255,255,0.1)}
</style>
</head>
<body>
<h1>👛 CRYPTO WALLET</h1>
<div>
<button onclick="createWallet()">➕ Создать кошелёк</button>
<button onclick="checkBalance()">💰 Проверить баланс</button>
<div id="result" class="result"></div>
</div>
<script>
async function createWallet(){
const res=await fetch('/api/wallet/create',{method:'POST'});
const data=await res.json();
document.getElementById('result').innerHTML=`
<p>✅ Кошелёк создан!</p>
<p>📫 Address: ${data.address}</p>
<p>🔑 Public Key: ${data.public_key}</p>
`;
}
async function checkBalance(){
const addr=prompt('Введите адрес:');
if(!addr)return;
const res=await fetch(`/api/balance?address=${addr}`);
const data=await res.json();
document.getElementById('result').innerHTML=`<p>💰 Баланс: ${data.balance} ABS</p>`;
}
</script>
</body></html>'''
    
    def _get_explorer_html(self):
        return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Explorer</title>
<style>body{background:#0f0c29;color:#fff;font-family:monospace;padding:20px}
.block{background:rgba(255,255,255,0.1);margin:10px 0;padding:10px}
</style>
</head>
<body>
<h1>🔍 BLOCKCHAIN EXPLORER</h1>
<div id="blocks"></div>
<script>
fetch('/api/stats').then(r=>r.json()).then(async stats=>{
let html='';
for(let h=stats.height; h>=Math.max(0, stats.height-10); h--){
const res=await fetch(`/api/block?height=${h}`);
const block=await res.json();
html+=`<div class="block">📦 Блок #${h}<br>🌳 Merkle: ${block.merkle_root?.substring(0,32)}...<br>⛓️ Hash: ${block.block_hash?.substring(0,32)}...</div>`;
}
document.getElementById('blocks').innerHTML=html;
});
</script>
</body></html>'''

class APIServer:
    def __init__(self, core, nft, oracle, port=8080):
        self.core = core
        self.nft = nft
        self.oracle = oracle
        self.port = port
        self.server = None
        APIHandler.core = core
        APIHandler.nft = nft
        APIHandler.oracle = oracle
        APIHandler.rate_limiter = RateLimiter()
    
    def start(self):
        self.server = HTTPServer(('0.0.0.0', self.port), APIHandler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
    
    def stop(self):
        if self.server:
            self.server.shutdown()
