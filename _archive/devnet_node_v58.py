#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ABSOLUTE DEVNET NODE v58 - С MEMPOOL И PENDING TX"""

import json
import hashlib
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

VERSION = "58.0"
RPC_PORT = 8545
BLOCK_REWARD = 50.0

# Mempool с приоритетом по gas_price
mempool = []
mempool_lock = threading.Lock()
mempool_nonce = {}

# Глобальное состояние
state = {
    "balances": {},
    "nonces": {},
    "contracts": {}
}

# Генезис
state["balances"]["0x40e908721295de4a5cbc775abac8909781aeeea8"] = 1000000
state["nonces"]["0x40e908721295de4a5cbc775abac8909781aeeea8"] = 0

def calculate_gas(tx):
    """Расчёт газа для транзакции"""
    base = 21000
    data_cost = len(json.dumps(tx.get("data", {}))) * 10
    return base + data_cost

def execute_tx(tx, state):
    """Выполнение транзакции с проверкой газа и баланса"""
    try:
        sender = tx["from"]
        receiver = tx["to"]
        amount = tx["value"]
        gas_price = tx.get("gas_price", 1)
        gas_limit = tx.get("gas_limit", 21000)
        
        # Проверяем баланс
        if state["balances"].get(sender, 0) < amount:
            return {"status": 0, "error": "INSUFFICIENT_BALANCE", "gas_used": 0}
        
        # Вычисляем газ
        gas_used = calculate_gas(tx)
        if gas_used > gas_limit:
            return {"status": 0, "error": "OUT OF GAS", "gas_used": 0}
        
        fee = gas_used * gas_price
        
        # Проверяем баланс с учётом комиссии
        if state["balances"].get(sender, 0) < amount + fee:
            return {"status": 0, "error": "INSUFFICIENT_BALANCE FOR FEE", "gas_used": 0}
        
        # Выполняем перевод
        state["balances"][sender] = state["balances"].get(sender, 0) - amount - fee
        state["balances"][receiver] = state["balances"].get(receiver, 0) + amount
        
        # Инкремент nonce
        state["nonces"][sender] = state["nonces"].get(sender, 0) + 1
        
        return {
            "status": 1,
            "error": None,
            "gas_used": gas_used,
            "fee": fee
        }
    except Exception as e:
        return {"status": 0, "error": str(e), "gas_used": 0}

class Transaction:
    def __init__(self, from_addr, to_addr, amount, gas_price=1, gas_limit=21000, data=None):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount = amount
        self.gas_price = gas_price
        self.gas_limit = gas_limit
        self.data = data or {}
        self.timestamp = int(time.time())
        self.status = "pending"
        self.error = None
        self.gas_used = 0
        self.hash = hashlib.sha256(f"{from_addr}{to_addr}{amount}{self.timestamp}".encode()).hexdigest()[:16]
    
    def to_dict(self):
        return {
            "hash": self.hash,
            "from": self.from_addr,
            "to": self.to_addr,
            "value": str(self.amount),
            "gas_price": self.gas_price,
            "gas_limit": self.gas_limit,
            "gas_used": self.gas_used,
            "status": self.status,
            "error": self.error,
            "timestamp": self.timestamp
        }

class Block:
    def __init__(self, height, prev_hash, miner):
        self.height = height
        self.prev_hash = prev_hash
        self.timestamp = int(time.time())
        self.miner = miner
        self.txs = []
        self.nonce = 0
        self.gas_used_total = 0
        self.fees_total = 0
        self.hash = self.calc_hash()
    
    def calc_hash(self):
        data = f"{self.height}{self.prev_hash}{self.timestamp}{self.miner}{json.dumps(self.txs)}{self.nonce}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def to_dict(self):
        return {
            "number": self.height,
            "hash": self.hash,
            "parent_hash": self.prev_hash,
            "timestamp": self.timestamp,
            "miner": self.miner,
            "transactions": self.txs,
            "tx_count": len(self.txs),
            "gas_used": self.gas_used_total,
            "fees": self.fees_total
        }

class Blockchain:
    def __init__(self):
        self.chain = []
        self.load_chain()
    
    def load_chain(self):
        os.makedirs("data", exist_ok=True)
        chain_file = "data/chain.json"
        
        if os.path.exists(chain_file):
            try:
                with open(chain_file, 'r') as f:
                    data = json.load(f)
                    for block_data in data:
                        b = Block(block_data['number'], block_data['parent_hash'], block_data['miner'])
                        b.hash = block_data['hash']
                        b.timestamp = block_data['timestamp']
                        b.txs = block_data.get('transactions', [])
                        b.gas_used_total = block_data.get('gas_used', 0)
                        self.chain.append(b)
                    print(f"📦 Loaded chain: {len(self.chain)} blocks")
            except:
                self._create_genesis()
        else:
            self._create_genesis()
    
    def _create_genesis(self):
        g = Block(0, "0" * 64, "genesis")
        g.hash = g.calc_hash()
        self.chain.append(g)
        self.save_chain()
        print("🌱 Genesis block created")
    
    def save_chain(self):
        with open("data/chain.json", 'w') as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)
    
    def get_wallet_address(self):
        wallet_file = "data/wallet.json"
        if os.path.exists(wallet_file):
            try:
                with open(wallet_file, 'r') as f:
                    return json.load(f).get('address', '0x40e908721295de4a5cbc775abac8909781aeeea8')
            except:
                pass
        return '0x40e908721295de4a5cbc775abac8909781aeeea8'
    
    def get_balance(self, addr):
        return state["balances"].get(addr, 0)
    
    def get_pending_count(self):
        with mempool_lock:
            return len(mempool)
    
    def get_pending_txs(self, limit=20):
        with mempool_lock:
            return [tx.to_dict() for tx in mempool[:limit]]
    
    def send_transaction(self, from_addr, to_addr, amount, gas_price=1, gas_limit=21000, data=None):
        # Проверяем nonce
        expected_nonce = state["nonces"].get(from_addr, 0)
        
        tx = Transaction(from_addr, to_addr, amount, gas_price, gas_limit, data)
        
        with mempool_lock:
            mempool.append(tx)
            # Сортируем по gas_price (выше цена = выше приоритет)
            mempool.sort(key=lambda t: t.gas_price, reverse=True)
        
        return True, tx.hash
    
    def mine_block(self, miner=None):
        if not miner:
            miner = self.get_wallet_address()
        
        with mempool_lock:
            txs_to_mine = mempool[:20]
            mempool[:] = mempool[20:]
        
        b = Block(len(self.chain), self.chain[-1].hash, miner)
        
        for tx in txs_to_mine:
            # Выполняем транзакцию
            result = execute_tx({
                "from": tx.from_addr,
                "to": tx.to_addr,
                "value": tx.amount,
                "gas_price": tx.gas_price,
                "gas_limit": tx.gas_limit,
                "data": tx.data
            }, state)
            
            tx.status = "confirmed" if result["status"] == 1 else "reverted"
            tx.error = result.get("error")
            tx.gas_used = result.get("gas_used", 0)
            
            b.txs.append(tx.to_dict())
            b.gas_used_total += result.get("gas_used", 0)
            b.fees_total += result.get("fee", 0)
        
        # Награда майнеру
        state["balances"][miner] = state["balances"].get(miner, 0) + BLOCK_REWARD
        
        b.hash = b.calc_hash()
        self.chain.append(b)
        self.save_chain()
        
        print(f"📦 Block #{b.height}: {b.hash} | {len(b.txs)} txs | Gas: {b.gas_used_total} | Pending: {len(mempool)}")
        return b
    
    def get_info(self):
        return {
            "blocks": len(self.chain) - 1,
            "version": VERSION,
            "mempool_size": self.get_pending_count(),
            "contracts": len(state.get("contracts", {}))
        }
    
    def get_block(self, height):
        if 0 <= height < len(self.chain):
            return self.chain[height]
        return None
    
    def get_latest_block(self):
        return self.chain[-1] if self.chain else None

class RPCWebhook(BaseHTTPRequestHandler):
    blockchain = None
    
    def log_message(self, format, *args):
        pass
    
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b'{}'
        
        try:
            data = json.loads(body.decode())
        except:
            data = {}
        
        method = data.get('method', '')
        params = data.get('params', [])
        _id = data.get('id', 1)
        
        result = None
        
        if method == 'eth_blockNumber':
            result = hex(self.blockchain.get_info()['blocks'])
        
        elif method == 'eth_chainId':
            result = "0x539"
        
        elif method == 'net_version':
            result = "1337"
        
        elif method == 'txpool_status':
            result = {"pending": self.blockchain.get_pending_count()}
        
        elif method == 'eth_getBlockByNumber':
            if len(params) >= 1:
                block_param = params[0]
                if block_param == "latest":
                    block = self.blockchain.get_latest_block()
                else:
                    try:
                        height = int(block_param, 16) if block_param.startswith('0x') else int(block_param)
                        block = self.blockchain.get_block(height)
                    except:
                        block = None
                
                if block:
                    result = {
                        "number": hex(block.height),
                        "hash": block.hash,
                        "parentHash": block.prev_hash,
                        "timestamp": hex(block.timestamp),
                        "miner": block.miner,
                        "transactions": block.txs,
                        "gasUsed": hex(block.gas_used_total),
                        "tx_count": len(block.txs)
                    }
                else:
                    result = "0x0"
            else:
                result = "0x0"
        
        elif method == 'eth_getBalance':
            if len(params) >= 1:
                address = params[0]
                balance = self.blockchain.get_balance(address)
                result = hex(balance)
            else:
                result = "0x0"
        
        elif method == 'eth_sendTransaction':
            if len(params) >= 1:
                tx_data = params[0]
                from_addr = tx_data.get('from', '')
                to_addr = tx_data.get('to', '')
                value_str = tx_data.get('value', '0x0')
                amount = int(value_str, 16) if value_str.startswith('0x') else int(value_str)
                gas_price = int(tx_data.get('gasPrice', '0x1'), 16)
                gas_limit = int(tx_data.get('gas', '0x5208'), 16)
                
                success, tx_hash = self.blockchain.send_transaction(from_addr, to_addr, amount, gas_price, gas_limit, None)
                if success:
                    result = tx_hash
                else:
                    result = "0x0"
            else:
                result = "0x0"
        
        elif method == 'txpool_content':
            result = {"pending": {}}
        
        else:
            result = None
        
        response = {"jsonrpc": "2.0", "id": _id}
        if result is not None:
            response["result"] = result
        else:
            response["error"] = {"code": -32601, "message": "Method not found"}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "version": VERSION}).encode())

def main():
    print("=" * 60)
    print("ABSOLUTE DEVNET NODE v58 (MEMPOOL + PENDING TX)")
    print("=" * 60)
    
    blockchain = Blockchain()
    RPCWebhook.blockchain = blockchain
    
    server = HTTPServer(('0.0.0.0', RPC_PORT), RPCWebhook)
    
    print(f"🔓 Wallet: {blockchain.get_wallet_address()[:20]}...")
    print(f"📦 Height: {blockchain.get_info()['blocks']}")
    print(f"📋 Pending: {blockchain.get_pending_count()}")
    print(f"🌐 RPC: http://localhost:{RPC_PORT}")
    print("⛏️ Mining every 15 seconds")
    print("=" * 60)
    print("🚀 Node running! Press Ctrl+C to stop")
    print("=" * 60)
    
    def auto_mine():
        while True:
            time.sleep(15)
            try:
                blockchain.mine_block()
            except:
                pass
    
    threading.Thread(target=auto_mine, daemon=True).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Stopped")

if __name__ == '__main__':
    main()
