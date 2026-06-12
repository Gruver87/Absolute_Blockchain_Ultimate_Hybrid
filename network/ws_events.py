# network/ws_events.py — normalize EventBus payloads for WebSocket broadcast

from typing import Any, Dict


def _field(obj: Any, *keys, default=None):
    """Read field from dict or object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] is not None:
                return obj[key]
        return default
    for key in keys:
        val = getattr(obj, key, None)
        if val is not None:
            return val
    return default


def normalize_block_event(block: Any) -> Dict:
    txs = _field(block, "transactions", default=[]) or []
    tx_count = _field(block, "tx_count", default=None)
    if tx_count is None:
        tx_count = len(txs) if isinstance(txs, list) else 0
    return {
        "height": int(_field(block, "height", "number", default=0) or 0),
        "hash": _field(block, "hash", "block_hash", default="") or "",
        "txs": int(tx_count),
        "timestamp": _field(block, "timestamp", default=0),
        "miner": _field(block, "miner", "proposer", default="") or "",
        "burned": float(_field(block, "total_burned", "burned", default=0) or 0),
        "state_root": _field(block, "state_root", default="") or "",
    }


def normalize_tx_event(tx: Any) -> Dict:
    return {
        "hash": _field(tx, "hash", "tx_hash", default="") or "",
        "from": _field(tx, "from_addr", "from", default="") or "",
        "to": _field(tx, "to_addr", "to", default="") or "",
        "value": float(_field(tx, "value", "amount", default=0) or 0),
        "block": _field(tx, "block_height", "block", default="pending"),
        "nonce": _field(tx, "nonce", default=0),
    }
