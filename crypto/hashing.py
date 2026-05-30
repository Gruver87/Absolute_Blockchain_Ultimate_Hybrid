# crypto/hashing.py
"""
Cryptographic hashing for blockchain
"""

import hashlib
import json
from typing import Any, Dict


class Hasher:
    """Blockchain hashing utilities"""
    
    @staticmethod
    def sha256(data: bytes) -> str:
        """SHA256 hash"""
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def keccak256(data: bytes) -> str:
        """Keccak-256 (Ethereum compatible)"""
        return hashlib.sha3_256(data).hexdigest()
    
    @staticmethod
    def hash_object(obj: Any) -> str:
        """Hash any JSON-serializable object"""
        if isinstance(obj, (dict, list)):
            encoded = json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()
        elif isinstance(obj, str):
            encoded = obj.encode()
        elif isinstance(obj, bytes):
            encoded = obj
        else:
            encoded = str(obj).encode()
        
        return hashlib.sha256(encoded).hexdigest()
    
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
        return hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()
    
    @staticmethod
    def merkle_root(hashes: list) -> str:
        """Compute Merkle root from transaction hashes"""
        if not hashes:
            return hashlib.sha256(b"empty").hexdigest()
        
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256((hashes[i] + hashes[i+1]).encode()).hexdigest()
                for i in range(0, len(hashes), 2)
            ]
        return hashes[0]
