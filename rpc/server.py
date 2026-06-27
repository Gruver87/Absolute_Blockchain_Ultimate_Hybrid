# -*- coding: utf-8 -*-
"""Legacy JSON-RPC server for v48 tests."""
from typing import Any, Dict, List, Optional


class JSONRPCServer:
    def __init__(self, node: Any, host: str = "127.0.0.1", port: int = 8545):
        self.node = node
        self.host = host
        self.port = port

    def _storage(self):
        return getattr(self.node, "storage", None)

    def eth_blockNumber(self, params: List) -> str:
        storage = self._storage()
        height = storage.get_latest_block_number() if storage else 0
        return hex(height)

    def eth_chainId(self, params: List) -> str:
        storage = self._storage()
        chain_id = storage.get_metadata("chain_id") if storage else "1337"
        return hex(int(chain_id))

    def eth_getBalance(self, params: List) -> str:
        address = params[0] if params else ""
        storage = self._storage()
        balance = storage.get_balance(address) if storage else 0
        return hex(int(balance))

    def eth_getBlockByNumber(self, params: List) -> Optional[Dict]:
        storage = self._storage()
        if not storage:
            return None
        if params and params[0] == "latest":
            return storage.get_latest_block()
        if params:
            return storage.get_block_by_number(int(params[0], 16) if isinstance(params[0], str) and params[0].startswith("0x") else int(params[0]))
        return None

    def net_version(self, params: List) -> str:
        return "1337"

    def web3_clientVersion(self, params: List) -> str:
        return "AbsoluteBlockchain/1.2.0"

    def handle_request(self, payload: Dict) -> Dict:
        method = payload.get("method", "")
        params = payload.get("params", [])
        if not hasattr(self, method):
            return {"jsonrpc": "2.0", "id": payload.get("id"), "error": {"code": -32601, "message": "method not found"}}
        try:
            result = getattr(self, method)(params)
            return {"jsonrpc": "2.0", "id": payload.get("id"), "result": result}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": payload.get("id"), "error": {"code": -32000, "message": str(exc)}}
