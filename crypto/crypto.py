#!/usr/bin/env python3
"""Cryptographic primitives - SECP256K1 via cryptography + SHA3-256"""

import hashlib
import secrets

from crypto import native
from crypto.secp256k1_backend import (
    CRYPTO_AVAILABLE,
    generate_keypair,
    sign,
    verify,
)


class Crypto:
    @staticmethod
    def _keccak256_hashfunc(message: bytes):
        """ECDSA-compatible hashfunc wrapper (`.digest()` like hashlib)."""
        digest = native.keccak256_digest(message)

        class _Digest:
            def digest(self):
                return digest

        return _Digest()

    @staticmethod
    def keccak256(data: bytes) -> bytes:
        """Ethereum-compatible Keccak-256."""
        return native.keccak256_digest(data)

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
        signature = sign(tx_hash, private_key, hashfunc=Crypto._keccak256_hashfunc)
        return signature.hex()

    @staticmethod
    def verify_tx(tx_hash: bytes, signature_hex: str, public_key_hex: str) -> bool:
        """Verify ECDSA signature"""
        return verify(
            tx_hash,
            bytes.fromhex(signature_hex),
            bytes.fromhex(public_key_hex),
            hashfunc=Crypto._keccak256_hashfunc,
        )


crypto = Crypto()
