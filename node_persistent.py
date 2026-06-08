# node_persistent.py v54 - CLEAN WORKING VERSION
import sys
import os
import json
import time
import hashlib
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.blockchain import Blockchain
from core.wallet_crypto import Wallet
from execution.mempool import Mempool


class RPCHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            request = json.loads(body)
            method = request.get('method')
            params = request.get('params', [])
            request_id = request.get('id', 1)
            result = self.server.rpc_server.handle_method(method, params)
            response = json.dumps({"jsonrpc": "2.0", "result": result, "id": request_id})
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response.encode())
        except Exception as e:
            error_response = json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}, "id": None})
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(error_response.encode())
    
    def log_message(self, format, *args):
        pass


class RPCServer:
    def __init__(self, node, port=8545):
        self.node = node
        self.port = port
        self.http_server = None
    
    def handle_method(self, method, params):
        if method == "eth_blockNumber":
            return hex(self.node.blockchain.get_height())
        elif method == "eth_chainId":
            return "0x539"
        elif method == "eth_getBalance":
            return "0xf4240"
        elif method == "eth_gasPrice":
            return "0x3b9aca00"
        elif method == "net_version":
            return "0x539"
        elif method == "web3_clientVersion":
            return "AbsoluteBlockchain/v54"
        elif method == "eth_sendTransaction":
            tx = params[0] if params else {}
            if self.node.mempool:
                tx_hash = self.node.mempool.add_transaction(tx)
                print(f"   📝 Transaction added: {tx_hash[:16]}...")
                return f"0x{tx_hash}"
            return "0x0"
        elif method == "eth_getMempoolSize":
            if self.node.mempool:
                return hex(self.node.mempool.get_pending_count())
            return "0x0"
        elif method == "eth_getTransactionCount":
            return "0x0"
        elif method == "net_peerCount":
            return "0x0"
        else:
            return None
    
    def start(self):
        self.http_server = HTTPServer(('0.0.0.0', self.port), RPCHandler)
        self.http_server.rpc_server = self
        thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        thread.start()
        print(f"🌐 JSON-RPC Server running on http://0.0.0.0:{self.port}")


class PersistentNode:
    def __init__(self):
        print("=" * 60)
        print("ABSOLUTE BLOCKCHAIN NODE v54")
        print("=" * 60)
        self.blockchain = Blockchain()
        self.mempool = Mempool()
        self.wallet = None
        self.running = True
        self._init_wallet()
        self._init_chain()
        self._start_rpc()
        self._start_mining()
    
    def _init_wallet(self):
        wallet_file = "data/wallet.json"
        if os.path.exists(wallet_file):
            with open(wallet_file, 'r') as f:
                data = json.load(f)
                self.wallet = Wallet()
                self.wallet.address = data.get('address')
                self.wallet.balance = data.get('balance', 1000000)
            print(f"🔓 Loaded wallet: {self.wallet.address[:16]}...")
        else:
            self.wallet = Wallet.create()
            os.makedirs("data", exist_ok=True)
            with open(wallet_file, 'w') as f:
                json.dump({'address': self.wallet.address, 'balance': 1000000}, f)
            print(f"🆕 Created wallet: {self.wallet.address[:16]}...")
    
    def _init_chain(self):
        if self.blockchain.get_height() == 0:
            genesis = self.blockchain.create_genesis_block()
            self.blockchain.add_block(genesis)
            print("📦 Genesis block created")
        else:
            print(f"📦 Chain height: {self.blockchain.get_height()}")
    
    def _start_rpc(self):
        self.rpc_server = RPCServer(self, 8545)
        self.rpc_server.start()
    
    def _start_mining(self):
        def mine():
            print("⛏️ Auto-mining started (block every 15 seconds)")
            while self.running:
                time.sleep(15)
                try:
                    mempool_size = self.mempool.get_pending_count()
                    height = self.blockchain.get_height()
                    prev_hash = '0'*16
                    if height > 0:
                        last = self.blockchain.get_latest_block()
                        if last:
                            prev_hash = last.get('hash', '0'*16)
                    
                    transactions = []
                    if mempool_size > 0:
                        transactions = self.mempool.get_sorted_transactions(100)
                    
                    block = {
                        'height': height,
                        'transactions': transactions,
                        'prev_hash': prev_hash,
                        'timestamp': time.time(),
                        'validator': self.wallet.address,
                        'nonce': 0,
                        'hash': None
                    }
                    
                    block_string = f"{block['height']}{block['transactions']}{block['prev_hash']}{block['timestamp']}{block['validator']}"
                    block['hash'] = hashlib.sha256(block_string.encode()).hexdigest()[:16]
                    
                    if self.blockchain.add_block(block):
                        if transactions:
                            tx_hashes = [tx.get('hash', '') for tx in transactions if tx.get('hash')]
                            self.mempool.remove_transactions(tx_hashes)
                            print(f"📦 Block #{block['height']}: {block['hash'][:16]}... | {len(transactions)} txs")
                        else:
                            print(f"📦 Block #{block['height']}: {block['hash'][:16]}... | 0 txs")
                except Exception as e:
                    print(f"❌ Mining error: {e}")
        
        thread = threading.Thread(target=mine, daemon=True)
        thread.start()
    
    def run(self):
        print(f"\n🚀 Node running!")
        print(f"   Wallet: {self.wallet.address[:16]}...")
        print(f"   Height: {self.blockchain.get_height()}")
        print(f"   RPC: http://localhost:8545")
        print(f"\nPress Ctrl+C to stop\n")
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️ Shutting down...")
            self.running = False


def main():
    node = PersistentNode()
    node.run()

if __name__ == "__main__":
    main()





