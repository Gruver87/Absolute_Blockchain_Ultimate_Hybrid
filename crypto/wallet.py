# crypto/wallet.py (COMPLETE REWRITE - NO INDENTATION ERRORS)
"""
Full crypto wallet with ECDSA signing for transactions
"""

import os
import json
import hashlib
import time
from typing import Optional, Dict
from dataclasses import dataclass

from crypto.secp256k1_backend import (
    CRYPTO_AVAILABLE as ECDSA_AVAILABLE,
    generate_keypair as _generate_secp_keypair,
    sign,
    verify,
)
from crypto.keys import KeyGenerator


@dataclass
class KeyPair:
    private_key: bytes
    public_key: bytes
    address: str


class Wallet:
    """Cryptocurrency wallet with ECDSA signing"""
    
    def __init__(self, keypair: KeyPair = None):
        self.keypair = keypair or self._generate_keypair()
    
    def _generate_keypair(self) -> KeyPair:
        """Generate new secp256k1 keypair"""
        if ECDSA_AVAILABLE:
            private_key, public_key = _generate_secp_keypair()
        else:
            private_key = os.urandom(32)
            public_key = hashlib.sha256(private_key).digest()
        
        address = self._derive_address(public_key)
        
        return KeyPair(
            private_key=private_key,
            public_key=public_key,
            address=address
        )
    
    def _derive_address(self, public_key: bytes) -> str:
        """Derive Ethereum-style address from public key"""
        sha = hashlib.sha256(public_key).digest()
        address_bytes = sha[-20:]
        return "0x" + address_bytes.hex()
    
    @property
    def address(self) -> str:
        return self.keypair.address
    
    @property
    def public_key(self) -> str:
        return self.keypair.public_key.hex()
    
    @property
    def private_key(self) -> str:
        return self.keypair.private_key.hex()
    
    def sign_transaction(self, to: str, value: int, nonce: int, chain_id: int = 1) -> dict:
        """Create and sign a transaction"""
        tx = {
            "from": self.address,
            "to": to,
            "value": value,
            "nonce": nonce,
            "chain_id": chain_id,
            "gas_limit": 21000,
            "gas_price": 1
        }
        
        tx_hash = self._hash_transaction(tx)
        signature = self._sign_hash(tx_hash)
        
        tx["signature"] = signature
        tx["public_key"] = self.public_key
        tx["hash"] = tx_hash
        
        return tx
    
    def _hash_transaction(self, tx: dict) -> str:
        """Create canonical hash of transaction for signing"""
        tx_for_hash = {
            "from": tx["from"],
            "to": tx["to"],
            "value": tx["value"],
            "nonce": tx["nonce"],
            "chain_id": tx["chain_id"]
        }
        encoded = json.dumps(tx_for_hash, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(encoded.encode()).hexdigest()
    
    def _sign_hash(self, data_hash: str) -> str:
        """Sign a hash with private key"""
        if not ECDSA_AVAILABLE:
            return hashlib.sha256((data_hash + self.private_key).encode()).hexdigest()
        
        signature = sign(data_hash.encode(), self.keypair.private_key, hashfunc=hashlib.sha256)
        return signature.hex()
    
    def sign_block(self, block: dict) -> str:
        """Sign a block as proposer"""
        block_hash = self._hash_block(block)
        return self._sign_hash(block_hash)
    
    def _hash_block(self, block: dict) -> str:
        block_for_hash = {
            "number": block.get("number"),
            "parent_hash": block.get("parent_hash"),
            "timestamp": block.get("timestamp"),
            "proposer": block.get("proposer")
        }
        encoded = json.dumps(block_for_hash, sort_keys=True)
        return hashlib.sha256(encoded.encode()).hexdigest()
    
    def sign_attestation(self, attestation: dict) -> str:
        """Sign an attestation as validator"""
        att_hash = self._hash_attestation(attestation)
        return self._sign_hash(att_hash)
    
    def _hash_attestation(self, attestation: dict) -> str:
        """Hash attestation for signing"""
        att_for_hash = {
            "validator": attestation.get("validator"),
            "target_hash": attestation.get("target_hash"),
            "target_height": attestation.get("target_height"),
            "slot": attestation.get("slot")
        }
        encoded = json.dumps(att_for_hash, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(encoded.encode()).hexdigest()
    
    def export(self, filepath: str, password: str = None):
        """Export wallet to file"""
        data = {
            "address": self.address,
            "public_key": self.public_key,
            "private_key": self.private_key
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def import_wallet(cls, filepath: str, password: str = None) -> "Wallet":
        """Import wallet from file"""
        with open(filepath, "r") as f:
            data = json.load(f)
        
        private_key = bytes.fromhex(data["private_key"])
        public_key = bytes.fromhex(data["public_key"])
        keypair = KeyPair(
            private_key=private_key,
            public_key=public_key,
            address=data["address"]
        )
        return cls(keypair)
    
    @classmethod
    def create_new(cls) -> "Wallet":
        return cls()
    
    @classmethod
    def from_private_key(cls, private_key_hex: str) -> "Wallet":
        private_key = bytes.fromhex(private_key_hex)
        public_key = KeyGenerator.private_to_public(private_key)
        address = KeyGenerator.derive_address(public_key)
        keypair = KeyPair(
            private_key=private_key,
            public_key=public_key,
            address=address
        )
        return cls(keypair)
    
    @classmethod
    def _derive_address(cls, public_key: bytes) -> str:
        sha = hashlib.sha256(public_key).digest()
        address_bytes = sha[-20:]
        return "0x" + address_bytes.hex()


# ========== SIGNATURE VERIFICATION ==========

def verify_transaction_signature(tx: dict) -> bool:
    """Verify transaction signature"""
    if "signature" not in tx or "public_key" not in tx:
        return False
    
    tx_to_verify = {
        "from": tx["from"],
        "to": tx["to"],
        "value": tx["value"],
        "nonce": tx["nonce"],
        "chain_id": tx.get("chain_id", 1)
    }
    
    tx_hash = json.dumps(tx_to_verify, sort_keys=True, separators=(',', ':'))
    tx_hash_hashed = hashlib.sha256(tx_hash.encode()).hexdigest()
    
    signature = bytes.fromhex(tx["signature"])
    public_key = bytes.fromhex(tx["public_key"])
    
    if not ECDSA_AVAILABLE:
        expected = hashlib.sha256((tx_hash_hashed + public_key.hex()).encode()).hexdigest()
        return signature.hex() == expected
    return verify(tx_hash_hashed.encode(), signature, public_key, hashfunc=hashlib.sha256)


def create_test_wallet() -> Wallet:
    return Wallet.create_new()
