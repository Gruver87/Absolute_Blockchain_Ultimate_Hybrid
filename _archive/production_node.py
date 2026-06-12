#!/usr/bin/env python3
"""PRODUCTION NODE - execution only, no DB writes"""

import json
import hashlib
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

VERSION = "60.0"
RPC_PORT = 8545
BLOCK_REWARD = 50.0
GAS_BASE = 21000

# Mempool
mempool = []
mempool_lock = threading.Lock()

# State (balances)
state = {"balances": {}, "nonces": {}}
state["balances"]["0x40e908721295de4a5cbc775abac8909781aeeea8"] = 1000000

class Transaction:
    def __init__(self, from_addr, to_addr, amount, gas_price=1, gas_limit=GAS_BASE):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount = amount
        self.gas_price = gas_price
        self.gas_limit = gas_limit
        self.timestamp = int(time.time())
        self.hash = hashlib.sha256(f"{from_addr}{to_addr}{amount}{self.timestamp}".encode()).hexdigest()[:16]

class Block:
    def __init__(self, height, prev_hash, miner):
        self.height = height
        self.prev_hash = prev_hash
        self.timestamp = int(time.time())
        self.miner = miner
        self.txs = []
        self.nonce = 0
        self.gas_used = 0
        self.hash = self.calc_hash()
    
    def calc_hash(self):
        data = f"{self.height}{self.prev_hash}{self.timestamp}{self.miner}{json.dumps(self.txs)}{self.nonce}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

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
                    for block_data in json.load(f):
                        b = Block(block_data['number'], block_data['parent_hash'], block_data['miner'])
                        b.hash = block_data['hash']
                        b.timestamp = block_data['timestamp']
                        b.txs = block_data.get('transactions', [])
                        b.gas_used = block_data.get('gas_used', 0)
                        self.chain.append(b)
                print(f"📦 Loaded chain: {len(self.chain)} blocks")
            except:
                self._create_genesis()
        else:
            self._create_genesis()
    
    def _create_genesis(self):
        g = Block(0, "0"*64, "genesis")
        g.hash = g.calc_hash()
        self.chain.append(g)
        self.save_chain()
        print("🌱 Genesis block created")
    
    def save_chain(self):
        with open("data/chain.json", 'w') as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)
    
    def get_wallet(self):
        return "0x40e908721295de4a5cbc775abac8909781aeeea8"
    
    def get_balance(self, addr):
        return state["balances"].get(addr, 0)
    
    def send_transaction(self, from_addr, to_addr, amount):
        if self.get_balance(from_addr) < amount:
            return False, "Insufficient balance"
        tx = Transaction(from_addr, to_addr, amount)
        with mempool_lock:
            mempool.append(tx)
        return True, tx.hash
    
    def mine_block(self, miner=None):
        if not miner:
            miner = self.get_wallet()
        
        with mempool_lock:
            txs_to_mine = mempool[:20]
            mempool[:] = mempool[20:]
        
        b = Block(len(self.chain), self.chain[-1].hash, miner)
        block_gas = 0
        
        for tx in txs_to_mine:
            tx_gas = GAS_BASE
            tx_fee = tx_gas * tx.gas_price
            
            if state["balances"].get(tx.from_addr, 0) < tx.amount + tx_fee:
                continue
            
            state["balances"][tx.from_addr] = state["balances"].get(tx.from_addr, 0) - tx.amount - tx_fee
            state["balances"][tx.to_addr] = state["balances"].get(tx.to_addr, 0) + tx.amount
            state["balances"][miner] = state["balances"].get(miner, 0) + tx_fee
            
            b.txs.append({"hash": tx.hash, "from": tx.from_addr, "to": tx.to_addr, "value": tx.amount})
            block_gas += tx_gas
        
        state["balances"][miner] = state["balances"].get(miner, 0) + BLOCK_REWARD
        b.gas_used = block_gas
        b.hash = b.calc_hash()
        self.chain.append(b)
        self.save_chain()
        
        print(f"📦 Block #{b.height}: {b.hash} | {len(b.txs)} txs | Gas: {block_gas} | Pending: {len(mempool)}")
        return b
    
    def to_dict(self):
        return {"blocks": len(self.chain)-1, "version": VERSION, "mempool_size": len(mempool)}
    
    def get_block(self, height):
        return self.chain[height] if 0 <= height < len(self.chain) else None
    
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
            result = hex(self.blockchain.to_dict()['blocks'])
        elif method == 'eth_chainId':
            result = "0x539"
        elif method == 'net_version':
            result = "1337"
        elif method == 'eth_getBalance':
            if params:
                result = hex(self.blockchain.get_balance(params[0]))
            else:
                result = "0x0"
        elif method == 'eth_sendTransaction':
            if params:
                tx = params[0]
                success, tx_hash = self.blockchain.send_transaction(tx.get('from'), tx.get('to'), int(tx.get('value', '0x0'), 16))
                result = tx_hash if success else "0x0"
            else:
                result = "0x0"
        elif method == 'eth_getBlockByNumber':
            if params:
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
                    result = {"number": hex(block.height), "hash": block.hash, "parentHash": block.prev_hash,
                              "timestamp": hex(block.timestamp), "miner": block.miner, "transactions": block.txs,
                              "gasUsed": hex(block.gas_used)}
                else:
                    result = "0x0"
            else:
                result = "0x0"
        else:
            result = None
        
        response = {"jsonrpc": "2.0", "id": _id}
        response["result"] = result if result is not None else "0x0"
        
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
    print("PRODUCTION NODE v60 (no DB writes)")
    print("=" * 60)
    
    blockchain = Blockchain()
    RPCWebhook.blockchain = blockchain
    
    server = HTTPServer(('0.0.0.0', RPC_PORT), RPCWebhook)
    
    print(f"🔓 Wallet: {blockchain.get_wallet()[:20]}...")
    print(f"📦 Height: {blockchain.to_dict()['blocks']}")
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

if __name__ == "__main__":
    main()
