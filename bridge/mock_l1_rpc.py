"""
In-process mock Ethereum JSON-RPC for bridge relayer CI / devnet.

Usage:
  from bridge.mock_l1_rpc import start_mock_l1_rpc, register_confirmed_tx
  server, url = start_mock_l1_rpc(15445)
  register_confirmed_tx("0xabc...", block_number=900)
  # set ETH_RPC_URL=url
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional, Tuple


class _MockL1Handler(BaseHTTPRequestHandler):
    """Minimal eth_getTransactionReceipt + eth_blockNumber."""

    registry: Dict[str, int] = {}
    head_block: int = 1000

    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._respond({"jsonrpc": "2.0", "id": 1, "error": {"code": -32700, "message": "parse"}})
            return

        method = body.get("method", "")
        params = body.get("params") or []
        req_id = body.get("id", 1)
        result = None

        if method == "eth_getTransactionReceipt":
            tx = str(params[0] if params else "").lower()
            entry = self.registry.get(tx)
            if entry is None:
                result = None
            elif isinstance(entry, dict):
                result = {
                    "blockNumber": hex(int(entry["block"])),
                    "status": entry.get("status", "0x1"),
                    "logs": entry.get("logs") or [],
                }
            else:
                result = {"blockNumber": hex(int(entry)), "status": "0x1", "logs": []}
        elif method == "eth_blockNumber":
            result = hex(self.head_block)
        elif method == "net_version":
            result = "1337"
        else:
            result = None

        self._respond({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _respond(self, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def register_confirmed_tx(
    tx_hash: str,
    block_number: int = 900,
    head_block: Optional[int] = None,
    status: str = "0x1",
    contract_address: Optional[str] = None,
) -> None:
    """Mark tx as mined with enough depth for default min_confirmations."""
    key = (tx_hash or "").strip().lower()
    if not key:
        return
    logs = []
    if contract_address:
        logs = [{"address": contract_address, "topics": [], "data": "0x"}]
    _MockL1Handler.registry[key] = {
        "block": int(block_number),
        "status": status,
        "logs": logs,
    }
    if head_block is not None:
        _MockL1Handler.head_block = int(head_block)
    else:
        _MockL1Handler.head_block = max(_MockL1Handler.head_block, int(block_number) + 20)


def clear_mock_registry() -> None:
    _MockL1Handler.registry.clear()
    _MockL1Handler.head_block = 1000


def start_mock_l1_rpc(host: str = "127.0.0.1", port: int = 15445) -> Tuple[HTTPServer, str]:
    """Start daemon thread mock RPC; returns (server, base_url)."""
    clear_mock_registry()
    server = HTTPServer((host, port), _MockL1Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name=f"mock-l1-{port}")
    thread.start()
    return server, f"http://{host}:{port}"
