#!/usr/bin/env python3
"""Cryptographic primitives - SECP256K1 via cryptography + SHA3-256"""

import hashlib
import secrets

from crypto.secp256k1_backend import (
    CRYPTO_AVAILABLE,
    generate_keypair,
    sign,
    verify,
)


class Crypto:
    @staticmethod
    def keccak256(data: bytes) -> bytes:
        """SHA3-256 (used as Keccak-256 in Ethereum)"""
        return hashlib.sha3_256(data).digest()

    @staticmethod
    def generate_keypair() -> tuple:
        """Generate (private_key_hex, public_key_hex, address_hex)"""
        private_key, public_key = generate_keypair()
        private_key_hex = private_key.hex()
        public_key_hex = public_key.hex()
        address = Crypto.keccak256(bytes.fromhex(public_key_hex))[-20:].hex()
        return private_key_hex, public_key_hex, f"0x{address}"

    @staticmethod
    def sign_tx(tx_hash: bytes, private_key_hex: str) -> str:
        """Sign transaction hash with private key"""
        private_key = bytes.fromhex(private_key_hex)
        signature = sign(tx_hash, private_key, hashfunc=hashlib.sha3_256)
        return signature.hex()

    @staticmethod
    def verify_tx(tx_hash: bytes, signature_hex: str, public_key_hex: str) -> bool:
        """Verify ECDSA signature"""
        return verify(
            tx_hash,
            bytes.fromhex(signature_hex),
            bytes.fromhex(public_key_hex),
            hashfunc=hashlib.sha3_256,
        )


crypto = Crypto()
