"""
L1 JSON-RPC helpers for bridge relayer (Ethereum-compatible chains).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def chain_rpc_url(chain: str) -> str:
    """Resolve RPC URL from env: ETH_RPC_URL, POLYGON_RPC_URL, etc."""
    aliases = {
        "ethereum": "ETH",
        "eth": "ETH",
        "bsc": "BSC",
        "binance": "BSC",
        "polygon": "POLYGON",
        "matic": "POLYGON",
    }
    norm = chain.lower().replace("-", "_")
    prefix = aliases.get(norm, norm.upper())
    key = f"{prefix}_RPC_URL"
    return os.environ.get(key, "").strip()


def min_confirmations() -> int:
    raw = os.environ.get("BRIDGE_MIN_CONFIRMATIONS", "12")
    try:
        return max(1, int(raw))
    except ValueError:
        return 12


def _rpc_call(rpc_url: str, method: str, params: list, timeout: float = 15) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(
        rpc_url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def _parse_hex_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    s = str(value)
    return int(s, 16) if s.startswith("0x") else int(s)


def get_block_number(rpc_url: str) -> int:
    result = _rpc_call(rpc_url, "eth_blockNumber", [])
    return _parse_hex_int(result)


def get_tx_confirmations(rpc_url: str, tx_hash: str) -> Optional[int]:
    """
    Return confirmation count for a mined tx, or None if not found / RPC error.
    """
    if not rpc_url or not tx_hash:
        return None
    try:
        receipt = _rpc_call(rpc_url, "eth_getTransactionReceipt", [tx_hash])
        if not receipt:
            return 0
        block_num = _parse_hex_int(receipt.get("blockNumber"))
        if block_num <= 0:
            return 0
        head = get_block_number(rpc_url)
        return max(0, head - block_num + 1)
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, ValueError, TimeoutError):
        return None


def is_tx_confirmed(rpc_url: str, tx_hash: str, required: Optional[int] = None) -> bool:
    need = required if required is not None else min_confirmations()
    conf = get_tx_confirmations(rpc_url, tx_hash)
    return conf is not None and conf >= need


def load_l1_queue(path: str) -> Dict[str, list]:
    if not path or not os.path.isfile(path):
        return {"outbound": [], "incoming": []}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "outbound": list(data.get("outbound", [])),
        "incoming": list(data.get("incoming", [])),
    }


def save_l1_queue(path: str, queue: Dict[str, list]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
