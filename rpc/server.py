# rpc/server.py
"""
JSON-RPC 2.0 Server for Blockchain API
Compatible with Ethereum JSON-RPC standard
"""

import json
import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class JSONRPCHandler(BaseHTTPRequestHandler):
    """JSON-RPC 2.0 request handler"""
    
    rpc_server = None
    
    def do_POST(self):
        """Handle POST requests"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            request = json.loads(body.decode('utf-8'))
            response = self.rpc_server.handle_request(request)
        except json.JSONDecodeError:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error"},
                "id": None
            }
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": None
            }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging


class JSONRPCServer:
    """JSON-RPC 2.0 Server"""
    
    def __init__(self, node, host: str = "0.0.0.0", port: int = 8545):
        self.node = node
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.running = False
        
        # Register methods
        self.methods = {}
        self._register_methods()
    
    def _register_methods(self):
        """Register all RPC methods"""
        # eth_ methods
        self.methods["eth_blockNumber"] = self.eth_blockNumber
        self.methods["eth_chainId"] = self.eth_chainId
        self.methods["eth_getBalance"] = self.eth_getBalance
        self.methods["eth_getBlockByNumber"] = self.eth_getBlockByNumber
        self.methods["eth_getBlockByHash"] = self.eth_getBlockByHash
        self.methods["eth_getTransactionByHash"] = self.eth_getTransactionByHash
        self.methods["eth_getTransactionReceipt"] = self.eth_getTransactionReceipt
        self.methods["eth_sendRawTransaction"] = self.eth_sendRawTransaction
        self.methods["eth_getCode"] = self.eth_getCode
        self.methods["eth_gasPrice"] = self.eth_gasPrice
        self.methods["eth_getLogs"] = self.eth_getLogs
        
        # net_ methods
        self.methods["net_version"] = self.net_version
        self.methods["net_peerCount"] = self.net_peerCount
        
        # web3_ methods
        self.methods["web3_clientVersion"] = self.web3_clientVersion
        self.methods["web3_sha3"] = self.web3_sha3
    
    def start(self):
        """Start JSON-RPC server"""
        JSONRPCHandler.rpc_server = self
        self.server = HTTPServer((self.host, self.port), JSONRPCHandler)
        self.running = True
        
        thread = threading.Thread(target=self._serve, daemon=True)
        thread.start()
        print(f"🌐 JSON-RPC Server running on http://{self.host}:{self.port}")
    
    def _serve(self):
        while self.running:
            self.server.handle_request()
    
    def stop(self):
        self.running = False
        if self.server:
            self.server.shutdown()
    
    def handle_request(self, request: dict) -> dict:
        """Handle JSON-RPC request"""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", [])
        
        if not method:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": req_id
            }
        
        handler = self.methods.get(method)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method {method} not found"},
                "id": req_id
            }
        
        try:
            result = handler(params)
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": req_id
            }
    
    # ========== eth_ METHODS ==========
    
    def eth_blockNumber(self, params) -> str:
        """Returns current block number as hex"""
        height = self.node.storage.get_latest_block_number()
        return hex(height)
    
    def eth_chainId(self, params) -> str:
        """Returns chain ID"""
        chain_id = self.node.storage.get_metadata("chain_id")
        if not chain_id:
            chain_id = "1"
        return hex(int(chain_id))
    
    def eth_getBalance(self, params) -> str:
        """Returns account balance in wei as hex"""
        if len(params) < 1:
            raise Exception("Missing address parameter")
        address = params[0]
        balance = self.node.storage.get_balance(address)
        return hex(balance)
    
    def eth_getBlockByNumber(self, params) -> Optional[dict]:
        """Returns block by number"""
        if len(params) < 1:
            raise Exception("Missing block parameter")
        
        block_param = params[0]
        include_txs = params[1] if len(params) > 1 else False
        
        if block_param == "latest":
            block = self.node.storage.get_latest_block()
        elif block_param == "earliest":
            block = self.node.storage.get_block_by_number(0)
        elif block_param.startswith("0x"):
            block_num = int(block_param, 16)
            block = self.node.storage.get_block_by_number(block_num)
        else:
            block = self.node.storage.get_block_by_number(int(block_param))
        
        if not block:
            return None
        
        return self._format_block(block, include_txs)
    
    def eth_getBlockByHash(self, params) -> Optional[dict]:
        """Returns block by hash"""
        if len(params) < 1:
            raise Exception("Missing hash parameter")
        
        block_hash = params[0]
        include_txs = params[1] if len(params) > 1 else False
        
        block = self.node.storage.get_block(block_hash)
        if not block:
            return None
        
        return self._format_block(block, include_txs)
    
    def eth_getTransactionByHash(self, params) -> Optional[dict]:
        """Returns transaction by hash"""
        if len(params) < 1:
            raise Exception("Missing hash parameter")
        
        tx_hash = params[0]
        # Would need transaction index in storage
        return None
    
    def eth_getTransactionReceipt(self, params) -> Optional[dict]:
        """Returns transaction receipt"""
        if len(params) < 1:
            raise Exception("Missing hash parameter")
        
        tx_hash = params[0]
        # Would need receipt storage
        return None
    
    def eth_sendRawTransaction(self, params) -> str:
        """Sends a signed transaction"""
        if len(params) < 1:
            raise Exception("Missing transaction data")
        
        raw_tx = params[0]
        # Decode and add to mempool
        # For now, return dummy hash
        import hashlib
        return "0x" + hashlib.sha256(raw_tx.encode()).hexdigest()[:64]
    
    def eth_getCode(self, params) -> str:
        """Returns contract code at address"""
        if len(params) < 1:
            raise Exception("Missing address parameter")
        
        address = params[0]
        # Would check if address is contract
        return "0x"
    
    def eth_gasPrice(self, params) -> str:
        """Returns current gas price in wei"""
        return hex(1_000_000_000)  # 1 Gwei
    
    def eth_getLogs(self, params) -> list:
        """Returns logs matching filter"""
        return []
    
    # ========== net_ METHODS ==========
    
    def net_version(self, params) -> str:
        """Returns network version"""
        return self.eth_chainId(params)
    
    def net_peerCount(self, params) -> str:
        """Returns number of connected peers"""
        count = self.node.peer_manager.get_peer_count() if hasattr(self.node, 'peer_manager') else 0
        return hex(count)
    
    # ========== web3_ METHODS ==========
    
    def web3_clientVersion(self, params) -> str:
        """Returns client version"""
        return f"AbsoluteBlockchain/v48"
    
    def web3_sha3(self, params) -> str:
        """Returns SHA3 hash of data"""
        if len(params) < 1:
            raise Exception("Missing data parameter")
        import hashlib
        data = params[0]
        if data.startswith("0x"):
            data = bytes.fromhex(data[2:])
        else:
            data = data.encode()
        return "0x" + hashlib.sha3_256(data).hexdigest()
    
    # ========== HELPERS ==========
    
    def _format_block(self, block: dict, include_txs: bool) -> dict:
        """Format block for JSON-RPC response"""
        return {
            "number": hex(block.get("number", 0)),
            "hash": block.get("hash", "0x0"),
            "parentHash": block.get("parent_hash", "0x0"),
            "timestamp": hex(block.get("timestamp", 0)),
            "proposer": block.get("proposer", "0x0"),
            "stateRoot": block.get("state_root", "0x0"),
            "transactionsRoot": block.get("tx_root", "0x0"),
            "transactions": block.get("transactions", []) if include_txs else [],
            "size": hex(len(json.dumps(block)))
        }
