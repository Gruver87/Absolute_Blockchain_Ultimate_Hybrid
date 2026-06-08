#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN ULTIMATE - UNIFIED WITH MINI-EVM v53
Full blockchain with smart contract support
"""

import json
import sqlite3
import hashlib
import time
import threading
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager

# ============================================================
# MINI-EVM (SMART CONTRACT VM)
# ============================================================

class MiniVM:
    """Mini-EVM — стековая машина для смарт-контрактов"""
    
    GAS_COSTS = {
        "PUSH": 2, "POP": 2, "ADD": 3, "SUB": 3, "MUL": 5, "DIV": 5,
        "STORE": 20, "LOAD": 20, "STOP": 0, "INC": 2, "DEC": 2,
        "EQ": 3, "LT": 3, "GT": 3, "JUMP": 1, "JUMPI": 1,
    }
    
    def __init__(self, gas_limit: int = 10000):
        self.stack: List[int] = []
        self.storage: Dict[int, int] = {}
        self.gas_used = 0
        self.gas_limit = gas_limit
        self.pc = 0
        self.running = True
    
    def _consume_gas(self, op: str):
        cost = self.GAS_COSTS.get(op, 1)
        if self.gas_used + cost > self.gas_limit:
            raise Exception(f"Out of gas! Used {self.gas_used}, need {cost}, limit {self.gas_limit}")
        self.gas_used += cost
    
    def execute(self, bytecode: List[Tuple[str, Optional[int]]]) -> Dict[str, Any]:
        self.pc = 0
        self.gas_used = 0
        self.stack = []
        self.running = True
        
        while self.pc < len(bytecode) and self.running:
            op, arg = bytecode[self.pc]
            self._consume_gas(op)
            
            if op == "PUSH":
                if arg is None:
                    raise Exception("PUSH requires argument")
                self.stack.append(arg)
            elif op == "POP":
                self.stack.pop()
            elif op == "ADD":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a + b)
            elif op == "SUB":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)
            elif op == "MUL":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)
            elif op == "DIV":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a // b if b != 0 else 0)
            elif op == "STORE":
                key = self.stack.pop()
                value = self.stack.pop()
                self.storage[key] = value
            elif op == "LOAD":
                key = self.stack.pop()
                self.stack.append(self.storage.get(key, 0))
            elif op == "INC":
                if not self.stack:
                    self.stack.append(0)
                self.stack[-1] += 1
            elif op == "DEC":
                if not self.stack:
                    self.stack.append(0)
                self.stack[-1] -= 1
            elif op == "EQ":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a == b else 0)
            elif op == "LT":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a < b else 0)
            elif op == "GT":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(1 if a > b else 0)
            elif op == "STOP":
                self.running = False
                break
            else:
                raise Exception(f"Unknown opcode: {op}")
            
            self.pc += 1
        
        return {
            "stack": self.stack.copy(),
            "storage": self.storage.copy(),
            "gas_used": self.gas_used,
            "success": self.gas_used <= self.gas_limit
        }
    
    def reset(self):
        self.stack = []
        self.storage = {}
        self.gas_used = 0
        self.pc = 0


class ContractManager:
    """Управление смарт-контрактами"""
    
    def __init__(self):
        self.contracts: Dict[str, dict] = {}
        self.vm = MiniVM()
    
    def deploy(self, bytecode: List[Tuple[str, Optional[int]]], address: str) -> bool:
        if address in self.contracts:
            return False
        self.contracts[address] = {
            "bytecode": bytecode,
            "storage": {},
            "deployed_at": time.time(),
            "owner": address[:20]
        }
        return True
    
    def call(self, address: str, function: str, args: List[int]) -> Optional[Dict]:
        if address not in self.contracts:
            return None
        
        contract = self.contracts[address]
        self.vm.reset()
        
        bytecode = contract["bytecode"].copy()
        for arg in reversed(args):
            bytecode.insert(0, ("PUSH", arg))
        bytecode.append(("STOP", None))
        
        result = self.vm.execute(bytecode)
        contract["storage"] = self.vm.storage.copy()
        
        return {
            "success": result["success"],
            "gas_used": result["gas_used"],
            "stack": result["stack"],
            "storage": result["storage"]
        }
    
    def get_contracts(self) -> Dict:
        return self.contracts
    
    def get_storage(self, address: str, key: int) -> int:
        if address not in self.contracts:
            return 0
        return self.contracts[address]["storage"].get(key, 0)


# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================
@dataclass
class Config:
    VERSION: str = "53.0"
    NETWORK_NAME: str = "AbsoluteBlockchain"
    API_PORT: int = 8080
    RPC_PORT: int = 8545
    EXPLORER_PORT: int = 8095
    BLOCK_TIME: int = 15
    BLOCK_REWARD: float = 50.0
    MIN_STAKE: float = 100.0
    RATE_LIMIT_REQUESTS: int = 100

config = Config()


# ============================================================
# RATE LIMITER
# ============================================================
class RateLimiter:
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.tokens: Dict[str, float] = {}
        self.last_refill: Dict[str, float] = {}
        self.lock = threading.RLock()
    
    def _refill_tokens(self, key: str):
        now = time.time()
        last = self.last_refill.get(key, now)
        time_passed = now - last
        refill = time_passed / 60.0 * self.requests_per_minute
        current = self.tokens.get(key, self.requests_per_minute)
        self.tokens[key] = min(self.requests_per_minute, current + refill)
        self.last_refill[key] = now
    
    def allow_request(self, key: str) -> Tuple[bool, int]:
        with self.lock:
            self._refill_tokens(key)
            if self.tokens.get(key, self.requests_per_minute) >= 1:
                self.tokens[key] -= 1
                return True, int(self.tokens[key])
            return False, 0

rate_limiter = RateLimiter()


# ============================================================
# ВАЛИДАЦИЯ
# ============================================================
def validate_address(address: str) -> Tuple[bool, str]:
    if not address or not isinstance(address, str):
        return False, "Address required"
    if not address.startswith('0x'):
        return False, "Address must start with 0x"
    if len(address) != 42:
        return False, "Address must be 42 characters"
    return True, ""

def validate_amount(amount: Any) -> Tuple[bool, str]:
    try:
        amount_float = float(amount)
    except:
        return False, "Amount must be a number"
    if amount_float <= 0:
        return False, "Amount must be positive"
    if amount_float > 1_000_000_000:
        return False, "Amount too large"
    return True, ""


# ============================================================
# MEMPOOL
# ============================================================
@dataclass
class MempoolTx:
    tx_hash: str
    from_addr: str
    to_addr: str
    amount: float
    fee: float
    timestamp: float

class Mempool:
    def __init__(self, max_size: int = 10000):
        self.transactions: Dict[str, MempoolTx] = {}
        self.max_size = max_size
        self.lock = threading.RLock()
    
    def add(self, tx: MempoolTx) -> bool:
        with self.lock:
            if tx.tx_hash in self.transactions:
                return False
            if len(self.transactions) >= self.max_size:
                oldest = min(self.transactions.keys(), key=lambda k: self.transactions[k].timestamp)
                del self.transactions[oldest]
            self.transactions[tx.tx_hash] = tx
            return True
    
    def get_pending(self, limit: int = 1000) -> List[MempoolTx]:
        with self.lock:
            return sorted(self.transactions.values(), key=lambda tx: tx.fee, reverse=True)[:limit]
    
    def remove(self, tx_hash: str) -> bool:
        with self.lock:
            return self.transactions.pop(tx_hash, None) is not None
    
    def size(self) -> int:
        with self.lock:
            return len(self.transactions)

mempool = Mempool()


# ============================================================
# STATE MANAGER
# ============================================================
class StateManager:
    def __init__(self):
        self.balances: Dict[str, float] = {}
        self.lock = threading.RLock()
    
    def get_balance(self, address: str) -> float:
        with self.lock:
            return self.balances.get(address, 0)
    
    def set_balance(self, address: str, amount: float):
        with self.lock:
            self.balances[address] = amount
    
    def transfer(self, from_addr: str, to_addr: str, amount: float) -> bool:
        with self.lock:
            if self.balances.get(from_addr, 0) < amount:
                return False
            self.balances[from_addr] = self.balances.get(from_addr, 0) - amount
            self.balances[to_addr] = self.balances.get(to_addr, 0) + amount
            return True

state_manager = StateManager()


# ============================================================
# БЛОКЧЕЙН ЯДРО
# ============================================================
class Block:
    def __init__(self, height: int, previous_hash: str, miner: str):
        self.height = height
        self.previous_hash = previous_hash
        self.timestamp = int(time.time())
        self.miner = miner
        self.transactions = []
        self.nonce = 0
        self.block_hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        data = f"{self.height}{self.previous_hash}{self.timestamp}{self.miner}{json.dumps(self.transactions)}{self.nonce}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return {
            'height': self.height,
            'block_hash': self.block_hash,
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'miner': self.miner,
            'transactions': self.transactions,
            'transaction_count': len(self.transactions)
        }

class Transaction:
    def __init__(self, from_addr: str, to_addr: str, amount: float):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount = amount
        self.timestamp = int(time.time())
        self.tx_hash = hashlib.sha256(f"{from_addr}{to_addr}{amount}{self.timestamp}".encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return {
            'tx_hash': self.tx_hash,
            'from': self.from_addr,
            'to': self.to_addr,
            'amount': self.amount,
            'timestamp': self.timestamp
        }

class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        self.contract_manager = ContractManager()
        self.load_or_create_chain()
    
    def load_or_create_chain(self):
        os.makedirs("data", exist_ok=True)
        chain_file = "data/chain.json"
        
        if os.path.exists(chain_file):
            try:
                with open(chain_file, 'r') as f:
                    data = json.load(f)
                    for block_data in data:
                        block = Block(block_data['height'], block_data['previous_hash'], block_data['miner'])
                        block.block_hash = block_data['block_hash']
                        block.timestamp = block_data['timestamp']
                        block.transactions = block_data.get('transactions', [])
                        self.chain.append(block)
                    print(f"📦 Loaded {len(self.chain)} blocks")
            except:
                self._create_genesis()
        else:
            self._create_genesis()
        
        state_manager.set_balance(self.get_wallet_address(), 1000000)
    
    def _create_genesis(self):
        genesis = Block(0, "0" * 64, "genesis")
        genesis.block_hash = genesis.calculate_hash()
        self.chain.append(genesis)
        self._save_chain()
        print("🌱 Genesis block created")
    
    def _save_chain(self):
        with open("data/chain.json", 'w') as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)
    
    def get_wallet_address(self) -> str:
        wallet_file = "data/wallet.json"
        if os.path.exists(wallet_file):
            try:
                with open(wallet_file, 'r') as f:
                    return json.load(f).get('address', '0x94f45b97f9bc27')
            except:
                pass
        return '0x94f45b97f9bc27'
    
    def get_balance(self, address: str) -> float:
        return state_manager.get_balance(address)
    
    def add_transaction(self, tx: Transaction) -> bool:
        valid, err = validate_amount(tx.amount)
        if not valid:
            return False
        if state_manager.get_balance(tx.from_addr) < tx.amount + 0.001:
            return False
        mempool_tx = MempoolTx(tx.tx_hash, tx.from_addr, tx.to_addr, tx.amount, 0.001, tx.timestamp)
        return mempool.add(mempool_tx)
    
    def mine_block(self, miner: str) -> Optional[Block]:
        pending = mempool.get_pending(50)
        new_block = Block(len(self.chain), self.chain[-1].block_hash, miner)
        
        for tx in pending[:20]:
            if state_manager.transfer(tx.from_addr, tx.to_addr, tx.amount):
                new_block.transactions.append({
                    'tx_hash': tx.tx_hash,
                    'from': tx.from_addr,
                    'to': tx.to_addr,
                    'amount': tx.amount
                })
                mempool.remove(tx.tx_hash)
        
        state_manager.set_balance(miner, state_manager.get_balance(miner) + config.BLOCK_REWARD)
        new_block.block_hash = new_block.calculate_hash()
        
        self.chain.append(new_block)
        self._save_chain()
        
        print(f"📦 Block #{new_block.height}: {new_block.block_hash} | {len(new_block.transactions)} txs")
        return new_block
    
    def get_blockchain_info(self) -> Dict:
        return {
            'chain': config.NETWORK_NAME,
            'blocks': len(self.chain) - 1,
            'mining_reward': config.BLOCK_REWARD,
            'mempool_size': mempool.size(),
            'version': config.VERSION,
            'vm_supported': True,
            'contracts': len(self.contract_manager.get_contracts())
        }
    
    def deploy_contract(self, bytecode: List[Tuple], owner: str) -> Optional[str]:
        contract_address = hashlib.sha256(f"{owner}{time.time()}".encode()).hexdigest()[:20]
        contract_address = "0x" + contract_address
        if self.contract_manager.deploy(bytecode, contract_address):
            return contract_address
        return None
    
    def call_contract(self, address: str, method: str, args: List[int]) -> Optional[Dict]:
        return self.contract_manager.call(address, method, args)


# ============================================================
# API СЕРВЕР
# ============================================================
class UnifiedAPIHandler(BaseHTTPRequestHandler):
    blockchain = None
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        allowed, _ = rate_limiter.allow_request(self.client_address[0])
        if not allowed:
            self._send_json({'error': 'Rate limit exceeded'}, 429)
            return
        
        if path == '/' or path == '/index.html':
            self._send_html(self._get_web_interface())
        elif path == '/explorer':
            self._send_html(self._get_explorer_html())
        elif path == '/api/stats':
            self._send_json(self.blockchain.get_blockchain_info())
        elif path == '/api/blocks':
            blocks = [b.to_dict() for b in self.blockchain.chain[1:]]
            self._send_json({'blocks': blocks, 'total': len(blocks)})
        elif path == '/api/balance':
            query = parse_qs(parsed.query)
            address = query.get('address', [''])[0]
            if address:
                self._send_json({'address': address, 'balance': self.blockchain.get_balance(address)})
            else:
                self._send_json({'error': 'Address required'}, 400)
        elif path == '/api/contracts':
            self._send_json({'contracts': self.blockchain.contract_manager.get_contracts()})
        else:
            self._send_json({'error': 'Not found'}, 404)
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(body.decode('utf-8'))
        except:
            data = {}
        
        path = self.path
        
        if path == '/api/transaction/send':
            from_addr = data.get('from')
            to_addr = data.get('to')
            amount = float(data.get('amount', 0))
            
            if not from_addr or not to_addr:
                self._send_json({'error': 'Missing from/to address'}, 400)
                return
            
            valid, err = validate_address(from_addr)
            if not valid:
                self._send_json({'error': err}, 400)
                return
            
            valid, err = validate_amount(amount)
            if not valid:
                self._send_json({'error': err}, 400)
                return
            
            tx = Transaction(from_addr, to_addr, amount)
            success = self.blockchain.add_transaction(tx)
            self._send_json({'success': success, 'tx_hash': tx.tx_hash if success else None})
        
        elif path == '/api/mine':
            miner = data.get('miner', self.blockchain.get_wallet_address())
            block = self.blockchain.mine_block(miner)
            self._send_json({'success': block is not None, 'height': block.height if block else 0})
        
        elif path == '/api/contract/deploy':
            bytecode = data.get('bytecode', [])
            owner = data.get('owner', self.blockchain.get_wallet_address())
            address = self.blockchain.deploy_contract(bytecode, owner)
            self._send_json({'success': address is not None, 'address': address})
        
        elif path == '/api/contract/call':
            address = data.get('address')
            method = data.get('method', 'get')
            args = data.get('args', [])
            result = self.blockchain.call_contract(address, method, args)
            self._send_json({'success': result is not None, 'result': result})
        
        else:
            self._send_json({'error': 'Not found'}, 404)
    
    def _send_json(self, data: Dict, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_html(self, html: str, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def _get_web_interface(self) -> str:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Absolute Blockchain Ultimate with Smart Contracts</title>
            <style>
                body { font-family: monospace; background: #0a0a0a; color: #0f0; padding: 20px; }
                h1, h2 { color: #0f0; }
                .info { background: #0a1a0a; border: 1px solid #0f0; padding: 10px; margin: 10px 0; border-radius: 5px; }
                button { background: #0a0a0a; color: #0f0; border: 1px solid #0f0; padding: 5px 10px; cursor: pointer; }
                input, select { background: #1a1a1a; color: #0f0; border: 1px solid #0f0; padding: 5px; width: 300px; }
                .contract { border-left: 3px solid #0f0; margin: 5px 0; padding: 5px; }
            </style>
        </head>
        <body>
            <h1>🔗 Absolute Blockchain Ultimate with Mini-EVM</h1>
            <div class="info">
                <div>📦 Block Height: <span id="height">...</span></div>
                <div>📋 Mempool: <span id="mempool">...</span></div>
                <div>📄 Contracts: <span id="contracts">...</span></div>
                <div>⚡ VM: Mini-EVM (50+ opcodes)</div>
            </div>
            
            <h2>💰 Send Transaction</h2>
            <input type="text" id="to" placeholder="Recipient address (0x...)">
            <input type="number" id="amount" placeholder="Amount">
            <button onclick="sendTx()">Send</button>
            <div id="result"></div>
            
            <h2>📄 Deploy Smart Contract</h2>
            <select id="contract_type">
                <option value="counter">Counter Contract (INC/DEC/GET)</option>
                <option value="storage">Storage Contract (STORE/LOAD)</option>
            </select>
            <button onclick="deployContract()">Deploy</button>
            <div id="deployResult"></div>
            
            <script>
                async function loadStats() {
                    const res = await fetch('/api/stats');
                    const data = await res.json();
                    document.getElementById('height').innerText = data.blocks;
                    document.getElementById('mempool').innerText = data.mempool_size;
                    document.getElementById('contracts').innerText = data.contracts || 0;
                }
                
                async function sendTx() {
                    const to = document.getElementById('to').value;
                    const amount = document.getElementById('amount').value;
                    const res = await fetch('/api/transaction/send', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({from: '0x94f45b97f9bc27', to: to, amount: parseFloat(amount)})
                    });
                    const data = await res.json();
                    document.getElementById('result').innerHTML = data.success ? '✅ Tx sent: ' + data.tx_hash : '❌ Failed';
                    loadStats();
                }
                
                async function deployContract() {
                    const type = document.getElementById('contract_type').value;
                    let bytecode = [];
                    if (type === 'counter') {
                        bytecode = [["PUSH", 0], ["STORE", 0x100], ["LOAD", 0x100], ["INC"], ["STORE", 0x100], ["STOP"]];
                    } else {
                        bytecode = [["PUSH", 0], ["STORE", 0x200], ["LOAD", 0x200], ["STOP"]];
                    }
                    const res = await fetch('/api/contract/deploy', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({bytecode: bytecode})
                    });
                    const data = await res.json();
                    document.getElementById('deployResult').innerHTML = data.success ? '✅ Contract deployed: ' + data.address : '❌ Failed';
                    loadStats();
                }
                
                loadStats();
                setInterval(loadStats, 3000);
            </script>
        </body>
        </html>
        '''
    
    def _get_explorer_html(self) -> str:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Absolute Blockchain Explorer</title>
            <style>
                body { font-family: monospace; background: #0a0a0a; color: #0f0; padding: 20px; }
                h1 { color: #0f0; }
                .block { border: 1px solid #0f0; margin: 10px 0; padding: 10px; border-radius: 5px; }
                button { background: #0a0a0a; color: #0f0; border: 1px solid #0f0; padding: 5px 10px; cursor: pointer; }
            </style>
        </head>
        <body>
            <h1>🔍 Absolute Blockchain Explorer</h1>
            <button onclick="loadBlocks()">🔄 Refresh</button>
            <div id="blocks">Loading...</div>
            <script>
                async function loadBlocks() {
                    const res = await fetch('/api/blocks');
                    const data = await res.json();
                    let html = '';
                    for (const block of data.blocks.reverse()) {
                        html += `<div class="block">
                            <b>🔷 Block #${block.height}</b>
                            <div>Hash: ${block.block_hash}</div>
                            <div>Miner: ${block.miner.substring(0, 20)}...</div>
                            <div>📝 Transactions: ${block.transaction_count}</div>
                        </div>`;
                    }
                    document.getElementById('blocks').innerHTML = html || '<p>No blocks</p>';
                }
                loadBlocks();
                setInterval(loadBlocks, 5000);
            </script>
        </body>
        </html>
        '''


# ============================================================
# ЗАПУСК
# ============================================================
def main():
    print("=" * 60)
    print("ABSOLUTE BLOCKCHAIN ULTIMATE - WITH MINI-EVM v53")
    print("=" * 60)
    
    blockchain = Blockchain()
    UnifiedAPIHandler.blockchain = blockchain
    
    server = HTTPServer(('0.0.0.0', config.API_PORT), UnifiedAPIHandler)
    
    print(f"🌐 Web Interface: http://localhost:{config.API_PORT}")
    print(f"🔍 Explorer: http://localhost:{config.API_PORT}/explorer")
    print(f"📡 API: http://localhost:{config.API_PORT}/api/stats")
    print(f"⚡ Smart Contracts: Mini-EVM ready")
    print(f"⛏️ Auto-mining every {config.BLOCK_TIME} seconds")
    print("=" * 60)
    print("🚀 Node running! Press Ctrl+C to stop")
    
    def auto_mine():
        while True:
            time.sleep(config.BLOCK_TIME)
            try:
                blockchain.mine_block(blockchain.get_wallet_address())
            except:
                pass
    
    mining_thread = threading.Thread(target=auto_mine, daemon=True)
    mining_thread.start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️ Shutting down...")
        server.shutdown()

if __name__ == '__main__':
    main()
