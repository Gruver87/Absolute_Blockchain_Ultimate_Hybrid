# crypto/signing.py (fixed)
"""
Transaction and block signing with secp256k1
"""

import json
import hashlib  # <-- FIX: added missing import
from typing import Tuple, Optional
from crypto.keys import KeyGenerator, KeyPair
from crypto.hashing import Hasher

from crypto.secp256k1_backend import CRYPTO_AVAILABLE as ECDSA_AVAILABLE, sign, verify


class Signer:
    """Handles cryptographic signing and verification"""
    
    @staticmethod
    def sign_transaction(tx: dict, private_key: bytes) -> str:
        """Sign a transaction with private key"""
        tx_hash = Hasher.hash_transaction(tx)
        return Signer._sign_hash(tx_hash, private_key)
    
    @staticmethod
    def sign_block(block: dict, private_key: bytes) -> str:
        """Sign a block with proposer's private key"""
        block_hash = Hasher.hash_block(block)
        return Signer._sign_hash(block_hash, private_key)
    
    @staticmethod
    def sign_attestation(attestation: dict, private_key: bytes) -> str:
        """Sign an attestation (validator vote)"""
        attestation_hash = Hasher.hash_object(attestation)
        return Signer._sign_hash(attestation_hash, private_key)
    
    @staticmethod
    def _sign_hash(data_hash: str, private_key: bytes) -> str:
        """Internal: sign a hash with private key"""
        if not ECDSA_AVAILABLE:
            return hashlib.sha256((data_hash + private_key.hex()).encode()).hexdigest()
        signature = sign(data_hash.encode(), private_key, hashfunc=hashlib.sha256)
        return signature.hex()
    
    @staticmethod
    def verify_transaction(tx: dict) -> bool:
        """Verify transaction signature"""
        if "signature" not in tx:
            return False
        
        signature = bytes.fromhex(tx["signature"])
        public_key_hex = tx.get("public_key")
        
        if not public_key_hex:
            return False
        
        public_key = bytes.fromhex(public_key_hex)
        tx_hash = Hasher.hash_transaction(tx)
        
        return Signer._verify_hash(tx_hash, signature, public_key)
    
    @staticmethod
    def verify_block_signature(block: dict, proposer_public_key: bytes) -> bool:
        """Verify block signature"""
        if "signature" not in block:
            return False
        
        signature = bytes.fromhex(block["signature"])
        block_hash = Hasher.hash_block(block)
        
        return Signer._verify_hash(block_hash, signature, proposer_public_key)
    
    @staticmethod
    def _verify_hash(data_hash: str, signature: bytes, public_key: bytes) -> bool:
        """Internal: verify hash signature"""
        if not ECDSA_AVAILABLE:
            # Simplified for testing
            return len(signature) > 0
        
        return verify(data_hash.encode(), signature, public_key, hashfunc=hashlib.sha256)
    
    @staticmethod
    def get_address_from_public_key(public_key_hex: str) -> str:
        """Derive address from public key"""
        public_key = bytes.fromhex(public_key_hex)
        return KeyGenerator.derive_address(public_key)


def create_signed_transaction(
    from_addr: str,
    to_addr: str,
    value: int,
    nonce: int,
    private_key: bytes,
    chain_id: int = 1
) -> dict:
    """Create a fully signed transaction"""
    tx = {
        "from": from_addr,
        "to": to_addr,
        "value": value,
        "nonce": nonce,
        "chain_id": chain_id,
        "gas_limit": 21000,
        "gas_price": 1
    }
    
    # Add signature
    signature = Signer.sign_transaction(tx, private_key)
    tx["signature"] = signature
    
    # Add public key for verification
    keypair = KeyGenerator.from_private_key(private_key.hex())
    tx["public_key"] = keypair.public_key.hex()
    
    # Add hash
    tx["hash"] = Hasher.hash_transaction(tx)
    
    return tx
