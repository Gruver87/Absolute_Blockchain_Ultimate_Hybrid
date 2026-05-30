# network/p2p/messages.py
"""
P2P message types: inventory, compact blocks, request/response
"""

import time
import hashlib
from typing import Dict, Any, Optional, List
from enum import Enum


class MessageType(Enum):
    """P2P message types"""
    HELLO = "hello"
    PING = "ping"
    PONG = "pong"
    INV_BLOCK = "inv_block"
    GET_BLOCK = "get_block"
    BLOCK = "block"
    INV_TX = "inv_tx"
    GET_TX = "get_tx"
    TX = "tx"
    GET_HEADERS = "get_headers"
    HEADERS = "headers"
    STATUS = "status"


class Message:
    """P2P message with inventory propagation"""
    
    def __init__(self, msg_type: MessageType, data: Any = None, request_id: str = None):
        self.type = msg_type
        self.data = data or {}
        self.request_id = request_id or self._generate_id()
        self.timestamp = time.time()
    
    def _generate_id(self) -> str:
        return hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:16]
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "data": self.data,
            "request_id": self.request_id,
            "timestamp": self.timestamp
        }
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        import json
        data = json.loads(json_str)
        return cls(
            msg_type=MessageType(data["type"]),
            data=data.get("data", {}),
            request_id=data.get("request_id")
        )


class InventoryMessage(Message):
    """Inventory message for block/tx announcements"""
    
    @classmethod
    def for_block(cls, block_hash: str) -> "InventoryMessage":
        return cls(MessageType.INV_BLOCK, {"hash": block_hash})
    
    @classmethod
    def for_tx(cls, tx_hash: str) -> "InventoryMessage":
        return cls(MessageType.INV_TX, {"hash": tx_hash})


class CompactBlock:
    """Compact block with transaction hashes instead of full txs"""
    
    def __init__(self, block_hash: str, block_number: int, tx_hashes: List[str]):
        self.block_hash = block_hash
        self.block_number = block_number
        self.tx_hashes = tx_hashes
    
    def to_dict(self) -> dict:
        return {
            "block_hash": self.block_hash,
            "block_number": self.block_number,
            "tx_hashes": self.tx_hashes
        }
    
    @classmethod
    def from_block(cls, block: dict):
        """Create compact block from full block"""
        tx_hashes = [tx.get("hash") for tx in block.get("transactions", [])]
        return cls(
            block_hash=block.get("hash"),
            block_number=block.get("number", 0),
            tx_hashes=tx_hashes
        )
    
    def reconstruct_block(self, mempool) -> dict:
        """Reconstruct full block from mempool txs"""
        transactions = []
        for tx_hash in self.tx_hashes:
            tx = mempool.get_transaction(tx_hash)
            if tx:
                transactions.append(tx)
        
        return {
            "hash": self.block_hash,
            "number": self.block_number,
            "transactions": transactions
        }
