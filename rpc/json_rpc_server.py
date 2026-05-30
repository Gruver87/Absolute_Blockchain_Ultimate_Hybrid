# rpc/json_rpc_server.py
"""
JSON-RPC 2.0 сервер для работы с контрактами
Поддерживает методы:
- eth_deployContract
- eth_call
- eth_sendTransaction
- eth_getStorageAt
- eth_chainId
- eth_gasPrice
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.contracts import ContractRegistry
from execution.contract_executor import ContractExecutor


class JSONRPCHandler(BaseHTTPRequestHandler):
    """Обработчик JSON-RPC запросов"""
    
    registry = None
    executor = None
    
    def do_POST(self):
        """Обработка POST запросов"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            request = json.loads(body.decode('utf-8'))
            response = self.handle_request(request)
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
                "id": None
            }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def handle_request(self, request: dict) -> dict:
        """Обработка JSON-RPC запроса"""
        method = request.get('method')
        params = request.get('params', [])
        req_id = request.get('id')
        
        handlers = {
            "eth_deployContract": self.handle_deploy,
            "eth_call": self.handle_call,
            "eth_sendTransaction": self.handle_send_transaction,
            "eth_getStorageAt": self.handle_get_storage,
            "eth_chainId": self.handle_chain_id,
            "eth_gasPrice": self.handle_gas_price,
            "eth_blockNumber": self.handle_block_number,
            "web3_clientVersion": self.handle_version,
        }
        
        handler = handlers.get(method)
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
    
    def handle_deploy(self, params: list) -> dict:
        """eth_deployContract — деплой контракта"""
        if len(params) < 2:
            raise Exception("Missing params: address, bytecode")
        
        address = params[0]
        bytecode = params[1]
        abi = params[2] if len(params) > 2 else {}
        
        success = self.executor.deploy_contract(address, bytecode, abi)
        return {"address": address, "success": success}
    
    def handle_call(self, params: list) -> dict:
        """eth_call — вызов метода (readonly)"""
        if len(params) < 2:
            raise Exception("Missing params: address, method")
        
        address = params[0]
        method = params[1]
        args = params[2] if len(params) > 2 else []
        
        result = self.executor.call_contract(address, method, args, readonly=True)
        return result
    
    def handle_send_transaction(self, params: list) -> dict:
        """eth_sendTransaction — отправка транзакции (write)"""
        if len(params) < 2:
            raise Exception("Missing params: address, method")
        
        address = params[0]
        method = params[1]
        args = params[2] if len(params) > 2 else []
        
        result = self.executor.call_contract(address, method, args, readonly=False)
        return result
    
    def handle_get_storage(self, params: list) -> dict:
        """eth_getStorageAt — получить storage по ключу"""
        if len(params) < 2:
            raise Exception("Missing params: address, key")
        
        address = params[0]
        key = int(params[1], 16) if isinstance(params[1], str) else params[1]
        
        value = self.executor.get_storage_at(address, key)
        return {"address": address, "key": key, "value": value}
    
    def handle_chain_id(self, params: list) -> str:
        return "0x1"
    
    def handle_gas_price(self, params: list) -> str:
        return "0x3B9ACA00"  # 1 Gwei
    
    def handle_block_number(self, params: list) -> str:
        return "0x1"
    
    def handle_version(self, params: list) -> str:
        return "AbsoluteBlockchain/v53"
    
    def log_message(self, format, *args):
        pass


def start_json_rpc_server(port: int = 8545, registry: ContractRegistry = None):
    """Запуск JSON-RPC сервера"""
    JSONRPCHandler.registry = registry or ContractRegistry()
    JSONRPCHandler.executor = ContractExecutor(JSONRPCHandler.registry)
    
    server = HTTPServer(('0.0.0.0', port), JSONRPCHandler)
    print(f"🌐 JSON-RPC Server running on http://localhost:{port}")
    print(f"   Available methods:")
    print(f"     - eth_deployContract")
    print(f"     - eth_call")
    print(f"     - eth_sendTransaction")
    print(f"     - eth_getStorageAt")
    print(f"     - eth_chainId")
    print(f"     - eth_gasPrice")
    print(f"     - web3_clientVersion")
    
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


if __name__ == "__main__":
    start_json_rpc_server()
