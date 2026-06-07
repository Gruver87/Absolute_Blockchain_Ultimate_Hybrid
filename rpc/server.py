# rpc/server.py - Fixed transaction handling
import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class JSONRPCHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            request = json.loads(body)
            method = request.get('method')
            params = request.get('params', [])
            request_id = request.get('id', 1)
            result = self.server.rpc_server._call_method(method, params)
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

class JSONRPCServer:
    def __init__(self, node, port=8545):
        self.node = node
        self.port = port
        self.http_server = None
        
    def _call_method(self, method, params):
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
            return "AbsoluteBlockchain/v52"
        
        elif method == "eth_sendTransaction":
            tx = params[0] if params else {}
            if hasattr(self.node, 'mempool'):
                tx_hash = self.node.mempool.add_transaction(tx)
                return f"0x{tx_hash}"
            return "0x0"
        
        elif method == "eth_getTransactionCount":
            return "0x0"
        
        elif method == "eth_getMempoolSize":
            if hasattr(self.node, 'mempool'):
                return hex(self.node.mempool.get_pending_count())
            return "0x0"
        
        elif method == "eth_getBlockTransactionCountByNumber":
            return "0x0"
        
        elif method == "net_peerCount":
            return "0x0"
        
        elif method == "eth_getBlockByNumber":
            block_num = params[0] if params else "latest"
            block = self.node.blockchain.get_latest_block()
            if block:
                return {"number": hex(block.height), "hash": block.hash, "transactions": []}
            return None
        
        else:
            raise Exception(f"Method {method} not found")
    
    def start(self):
        self.http_server = HTTPServer(('0.0.0.0', self.port), JSONRPCHandler)
        self.http_server.rpc_server = self
        thread = threading.Thread(target=lambda: self.http_server.serve_forever(), daemon=True)
        thread.start()
        print(f"🌐 JSON-RPC Server running on http://0.0.0.0:{self.port}")
    
    def stop(self):
        if self.http_server:
            self.http_server.shutdown()
