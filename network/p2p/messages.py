# -*- coding: utf-8 -*-
"""P2P message types for legacy tests."""
import json
from enum import Enum
from typing import Any, Dict, Optional


class MessageType(Enum):
    PING = "ping"
    PONG = "pong"
    INV_BLOCK = "inv_block"
    INV_TX = "inv_tx"
    BLOCK_ANNOUNCE = "block_announce"
    BLOCK_REQUEST = "block_request"
    BLOCK_RESPONSE = "block_response"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"


SNAPSHOT_REQUEST = "snapshot_request"
SNAPSHOT_RESPONSE = "snapshot_response"
STATE_ROOT_REQUEST = "state_root_request"
STATE_ROOT_RESPONSE = "state_root_response"


class Message:
    def __init__(self, msg_type: MessageType, data: Optional[Dict[str, Any]] = None):
        self.type = msg_type
        self.data = data or {}

    def to_json(self) -> str:
        return json.dumps({"type": self.type.value, "data": self.data})

    @classmethod
    def from_json(cls, raw: str) -> "Message":
        payload = json.loads(raw)
        return cls(MessageType(payload["type"]), payload.get("data", {}))


class InventoryMessage(Message):
    @classmethod
    def for_block(cls, block_hash: str) -> "InventoryMessage":
        return cls(MessageType.INV_BLOCK, {"hash": block_hash})

    @classmethod
    def for_tx(cls, tx_hash: str) -> "InventoryMessage":
        return cls(MessageType.INV_TX, {"hash": tx_hash})


class CompactBlock:
    def __init__(self, block_hash: str, tx_hashes: list):
        self.block_hash = block_hash
        self.tx_hashes = tx_hashes

    @classmethod
    def from_block(cls, block: Dict) -> "CompactBlock":
        txs = block.get("transactions", [])
        hashes = [tx.get("hash", str(i)) for i, tx in enumerate(txs)]
        return cls(block.get("hash", ""), hashes)


def create_block_announce(block_hash: str, height: int) -> Dict:
    return {"type": MessageType.BLOCK_ANNOUNCE.value, "hash": block_hash, "height": height}


def create_block_request(block_hash: str) -> Dict:
    return {"type": MessageType.BLOCK_REQUEST.value, "hash": block_hash}


def create_block_response(block: Dict) -> Dict:
    return {"type": MessageType.BLOCK_RESPONSE.value, "block": block}


def create_sync_request(from_height: int) -> Dict:
    return {"type": MessageType.SYNC_REQUEST.value, "from_height": from_height}


def create_sync_response(headers: list) -> Dict:
    return {"type": MessageType.SYNC_RESPONSE.value, "headers": headers}
