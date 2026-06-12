#!/usr/bin/env python3
"""LEVEL 12 NODE - Mini-Ethereum execution layer"""

import json
import hashlib
import time
import threading
import os
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

VERSION = "70.0"
RPC_PORT = 8545
BLOCK_REWARD = 50.0
GAS_PER_TX = 21000
MAX_TX_PER_BLOCK = 10

# ============================================================
# STATE (Balances, Nonces, Tokens)
# ============================================================
state = {
    "balances": {},
    "nonces": {},
    "tokens": {
        "ABS": {"name": "Absolute", "symbol": "ABS", "decimals": 18, "balances": {}},
        "DEV": {"name": "DevToken", "symbol": "DEV", "decimals": 18, "balances": {}}
    }
}

# Genesis addresses
GENESIS_ADDRESS = "0x40e908721295de4a5cbc775abac8909781aeeea8"
TEST_ADDRESSES = [
    "0x1234567890123456789012345678901234567890",
    "0x0987654321098765432109876543210987654321",
    "0x1111111111111111111111111111111111111111",
    "0x2222222222222222222222222222222222222222",
    "0x3333333333333333333333333333333333333333"
]

# Initialize genesis balances
state["balances"][GENESIS_ADDRESS] = 1_000_000
for addr in TEST_ADDRESSES:
    state["balances"][addr] = 100_000
    state["tokens"]["ABS"]["balances"][addr] = 10_000
    state["tokens"]["DEV"]["balances"][addr] = 5_000

# ============================================================
# MEMPOOL
# ============================================================
mempool = []
mempool_lock = threading.Lock()

# ============================================================
# TRANSACTION
# ============================================================
class Transaction:
    def __init__(self, from_addr, to_addr, amount, token="ABS", gas_price=1, nonce=None):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount = amount
        self.token = token
        self.gas_price = gas_price
        self.gas_used = GAS_PER_TX
        self.fee = self.gas_used * gas_price
        self.nonce = nonce
        self.timestamp = int(time.time())
        self.hash = hashlib.sha256(f"{from_addr}{to_addr}{amount}{token}{self.timestamp}".encode()).hexdigest()[:16]
    
    def to_dict(self):
        return {
            "hash": self.hash,
            "from": self.from_addr,
            "to": self.to_addr,
            "amount": self.amount,
            "token": self.token,
            "gas_used": self.gas_used,
            "gas_price": self.gas_price,
            "fee": self.fee,
            "nonce": self.nonce,
            "timestamp": self.timestamp
        }

# ============================================================
# BLOCK
# ============================================================
class Block:
    def __init__(self, height, prev_hash, miner):
        self.height = height
        self.prev_hash = prev_hash
        self.timestamp = int(time.time())
        self.miner = miner
        self.txs = []
        self.nonce = 0
        self.gas_used = 0
        self.state_root = ""
        self.hash = self.calc_hash()
    
    def calc_hash(self):
        data = f"{self.height}{self.prev_hash}{self.timestamp}{self.miner}{json.dumps(self.txs)}{self.nonce}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def compute_state_root(self):
        """Вычисление корня состояния (как в Ethereum)"""
        state_hash = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
        return state_hash[:16]
    
    def to_dict(self):
        return {
            "number": self.height,
            "hash": self.hash,
            "parent_hash": self.prev_hash,
            "timestamp": self.timestamp,
            "miner": self.miner,
            "transactions": self.txs,
            "tx_count": len(self.txs),
            "gas_used": self.gas_used,
            "state_root": self.state_root
        }

# ============================================================
# STATE MANAGEMENT
# ============================================================
def apply_transaction(tx):
    """Применение транзакции к состоянию"""
    # Проверка nonce
    expected_nonce = state["nonces"].get(tx.from_addr, 0)
    if tx.nonce is not None and tx.nonce != expected_nonce:
        return False, "Invalid nonce"
    
    # Проверка газа
    total_cost = tx.amount + tx.fee if tx.token == "ABS" else tx.fee
    
    if state["balances"].get(tx.from_addr, 0) < total_cost:
        return False, "Insufficient balance"
    
    # Списываем комиссию
    state["balances"][tx.from_addr] -= tx.fee
    state["balances"][tx.miner] = state["balances"].get(tx.miner, 0) + tx.fee
    
    # Переводим токены
    if tx.token == "ABS":
        state["balances"][tx.from_addr] -= tx.amount
        state["balances"][tx.to_addr] = state["balances"].get(tx.to_addr, 0) + tx.amount
    else:
        # Токен ERC20-lite
        token_balances = state["tokens"][tx.token]["balances"]
        if token_balances.get(tx.from_addr, 0) < tx.amount:
            return False, "Insufficient token balance"
        token_balances[tx.from_addr] = token_balances.get(tx.from_addr, 0) - tx.amount
        token_balances[tx.to_addr] = token_balances.get(tx.to_addr, 0) + tx.amount
    
    # Увеличиваем nonce
    state["nonces"][tx.from_addr] = expected_nonce + 1
    
    return True, "Success"

def generate_test_transaction():
    """Генерация тестовой транзакции"""
    from_addr = GENESIS_ADDRESS
    to_addr = random.choice(TEST_ADDRESSES)
    amount = random.randint(1, 50)
    token = random.choice(["ABS", "DEV"])
    nonce = state["nonces"].get(from_addr, 0)
    
    return Transaction(from_addr, to_addr, amount, token, 1, nonce)

# ============================================================
# BLOCKCHAIN CORE
# ============================================================
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
                        b.state_root = block_data.get('state_root', '')
                        self.chain.append(b)
                print(f"📦 Loaded chain: {len(self.chain)} blocks")
            except:
                self._create_genesis()
        else:
            self._create_genesis()
    
    def _create_genesis(self):
        g = Block(0, "0"*64, "genesis")
        g.state_root = g.compute_state_root()
        g.hash = g.calc_hash()
        self.chain.append(g)
        self.save_chain()
        print("🌱 Genesis block created")
    
    def save_chain(self):
        with open("data/chain.json", 'w') as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)
    
    def get_wallet(self):
        return GENESIS_ADDRESS
    
    def get_balance(self, addr):
        return state["balances"].get(addr, 0)
    
    def get_token_balance(self, addr, token="ABS"):
        return state["tokens"].get(token, {}).get("balances", {}).get(addr, 0)
    
    def send_transaction(self, from_addr, to_addr, amount, token="ABS"):
        nonce = state["nonces"].get(from_addr, 0)
        tx = Transaction(from_addr, to_addr, amount, token, 1, nonce)
        with mempool_lock:
            mempool.append(tx)
        return True, tx.hash
    
    def mine_block(self, miner=None):
        if not miner:
            miner = self.get_wallet()
        
        # Генерируем 1-3 тестовых транзакции
        for _ in range(random.randint(1, 3)):
            self.send_transaction(
                GENESIS_ADDRESS,
                random.choice(TEST_ADDRESSES),
                random.randint(1, 50),
                random.choice(["ABS", "DEV"])
            )
        
        with mempool_lock:
            txs_to_mine = mempool[:MAX_TX_PER_BLOCK]
            mempool[:] = mempool[MAX_TX_PER_BLOCK:]
        
        b = Block(len(self.chain), self.chain[-1].hash, miner)
        block_gas = 0
        
        for tx in txs_to_mine:
            success, msg = apply_transaction(tx)
            if success:
                b.txs.append(tx.to_dict())
                block_gas += tx.gas_used
            else:
                print(f"   ⚠️ Tx failed: {msg}")
        
        # Награда майнеру
        state["balances"][miner] = state["balances"].get(miner, 0) + BLOCK_REWARD
        
        b.gas_used = block_gas
        b.state_root = b.compute_state_root()
        b.hash = b.calc_hash()
        self.chain.append(b)
        self.save_chain()
        
        print(f"📦 Block #{b.height}: {b.hash[:16]} | {len(b.txs)} txs | Gas: {block_gas} | Pending: {len(mempool)}")
        return b
    
    def get_info(self):
        return {
            "blocks": len(self.chain)-1,
            "version": VERSION,
            "mempool_size": len(mempool),
            "gas_per_tx": GAS_PER_TX
        }
    
    def get_block(self, height):
        return self.chain[height] if 0 <= height < len(self.chain) else None
    
    def get_latest_block(self):
        return self.chain[-1] if self.chain else None

# ============================================================
# RPC SERVER
# ============================================================
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
        elif method == 'eth_getBalance':
            if params:
                result = hex(self.blockchain.get_balance(params[0]))
            else:
                result = "0x0"
        elif method == 'eth_getTokenBalance':
            if len(params) >= 2:
                result = hex(self.blockchain.get_token_balance(params[0], params[1]))
            else:
                result = "0x0"
        elif method == 'eth_sendTransaction':
            if params:
                tx = params[0]
                success, tx_hash = self.blockchain.send_transaction(
                    tx.get('from'), tx.get('to'), 
                    int(tx.get('value', '0x0'), 16),
                    tx.get('token', 'ABS')
                )
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
                    result = {
                        "number": hex(block.height),
                        "hash": block.hash,
                        "parentHash": block.prev_hash,
                        "timestamp": hex(block.timestamp),
                        "miner": block.miner,
                        "transactions": block.txs,
                        "gasUsed": hex(block.gas_used),
                        "stateRoot": block.state_root
                    }
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
    print("🔥 LEVEL 12 NODE - Mini-Ethereum Execution Layer")
    print("=" * 60)
    
    blockchain = Blockchain()
    RPCWebhook.blockchain = blockchain
    
    server = HTTPServer(('0.0.0.0', RPC_PORT), RPCWebhook)
    
    print(f"🔓 Wallet: {blockchain.get_wallet()[:20]}...")
    print(f"📦 Height: {blockchain.get_info()['blocks']}")
    print(f"📋 Mempool: {blockchain.get_info()['mempool_size']}")
    print(f"⛽ Gas per tx: {GAS_PER_TX}")
    print(f"🪙 Tokens: ABS, DEV")
    print(f"🌐 RPC: http://localhost:{RPC_PORT}")
    print("⛏️ Mining every 15 seconds (auto-tx enabled)")
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
