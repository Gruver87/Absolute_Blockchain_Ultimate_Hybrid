#!/usr/bin/env python3
"""Cryptographic primitives - ECDSA secp256k1 + SHA3-256"""

import hashlib
from ecdsa import SigningKey, VerifyingKey, SECP256k1
from ecdsa.util import sigencode_der, sigdecode_der
import secrets

class Crypto:
    @staticmethod
    def keccak256(data: bytes) -> bytes:
        """SHA3-256 (used as Keccak-256 in Ethereum)"""
        return hashlib.sha3_256(data).digest()
    
    @staticmethod
    def generate_keypair() -> tuple:
        """Generate (private_key_hex, public_key_hex, address_hex)"""
        sk = SigningKey.generate(curve=SECP256k1)
        vk = sk.get_verifying_key()
        
        private_key = sk.to_string().hex()
        public_key = vk.to_string().hex()
        
        # Address = last 20 bytes of keccak256(public_key)
        address = Crypto.keccak256(bytes.fromhex(public_key))[-20:].hex()
        
        return private_key, public_key, f"0x{address}"
    
    @staticmethod
    def sign_tx(tx_hash: bytes, private_key_hex: str) -> str:
        """Sign transaction hash with private key"""
        sk = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
        signature = sk.sign(tx_hash, hashfunc=hashlib.sha3_256, sigencode=sigencode_der)
        return signature.hex()
    
    @staticmethod
    def verify_tx(tx_hash: bytes, signature_hex: str, public_key_hex: str) -> bool:
        """Verify ECDSA signature"""
        try:
            vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
            return vk.verify(bytes.fromhex(signature_hex), tx_hash, 
                           hashfunc=hashlib.sha3_256, sigdecode=sigdecode_der)
        except:
            return False

crypto = Crypto()
