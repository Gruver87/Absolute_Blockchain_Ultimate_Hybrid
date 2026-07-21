# crypto/hashing.py
"""
Cryptographic hashing for blockchain
"""

import hashlib
import json
from typing import Any, Dict

from crypto import native


class Hasher:
    """Blockchain hashing utilities"""
    
    @staticmethod
    def sha256(data: bytes) -> str:
        """SHA256 hash"""
        return native.sha256_hex(data)
    
    @staticmethod
    def keccak256(data: bytes) -> str:
        """Ethereum-compatible Keccak-256."""
        return native.keccak256_hex(data)
    
    @staticmethod
    def hash_object(obj: Any) -> str:
        """Hash any JSON-serializable object"""
        if isinstance(obj, (dict, list)):
            encoded = json.dumps(obj, sort_keys=True, separators=(',', ':'))
            return native.hash_sorted_json(encoded)
        if isinstance(obj, str):
            return native.sha256_hex(obj.encode())
        if isinstance(obj, bytes):
            return native.sha256_hex(obj)
        return native.sha256_hex(str(obj).encode())
    
    @staticmethod
    def hash_transaction(tx: Dict) -> str:
        """Hash a transaction for signing"""
        tx_for_hash = {
            "from": tx.get("from"),
            "to": tx.get("to"),
            "value": tx.get("value"),
            "nonce": tx.get("nonce"),
            "chain_id": tx.get("chain_id", 1),
            "gas_limit": tx.get("gas_limit", 21000),
            "gas_price": tx.get("gas_price", 1)
        }
        return Hasher.hash_object(tx_for_hash)
    
    @staticmethod
    def hash_block(block: Dict) -> str:
        """Hash a block (without signature)"""
        block_for_hash = {
            "number": block.get("number"),
            "parent_hash": block.get("parent_hash"),
            "timestamp": block.get("timestamp"),
            "proposer": block.get("proposer"),
            "state_root": block.get("state_root"),
            "tx_root": block.get("tx_root")
        }
        return Hasher.hash_object(block_for_hash)
    
    @staticmethod
    def double_sha256(data: bytes) -> str:
        """Bitcoin-style double SHA256"""
        return native.double_sha256_hex(data)
    
    @staticmethod
    def merkle_root(hashes: list) -> str:
        """Compute Merkle root from transaction hashes"""
        if not hashes:
            return native.sha256_hex(b"empty")

        layer = list(hashes)
        while len(layer) > 1:
            if len(layer) % 2 == 1:
                layer.append(layer[-1])
            layer = [
                native.sha256_hex((layer[i] + layer[i + 1]).encode())
                for i in range(0, len(layer), 2)
            ]
        return layer[0]
