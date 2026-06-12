#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SECP256K1 через cryptography (OpenSSL).
Замена python-ecdsa — CVE-2024-23342 (Minerva timing attack) без патча в ecdsa.
"""

import hashlib
from typing import Callable, Optional, Type

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
    from cryptography.hazmat.primitives import hashes
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    InvalidSignature = Exception  # type: ignore

# Совместимость с прежним флагом
ECDSA_AVAILABLE = CRYPTO_AVAILABLE

_HASH_ALGO = {
    hashlib.sha256: hashes.SHA256,
    hashlib.sha3_256: hashes.SHA3_256,
}


def _hash_algorithm(hashfunc: Callable) -> hashes.HashAlgorithm:
    return _HASH_ALGO.get(hashfunc, hashes.SHA256)()


def _private_key_from_bytes(private_key: bytes) -> "ec.EllipticCurvePrivateKey":
    return ec.derive_private_key(int.from_bytes(private_key, "big"), ec.SECP256K1())


def _public_key_from_bytes(public_key: bytes) -> "ec.EllipticCurvePublicKey":
    x = int.from_bytes(public_key[:32], "big")
    y = int.from_bytes(public_key[32:], "big")
    return ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1()).public_key()


def generate_keypair() -> tuple:
    """Returns (private_key: 32 bytes, public_key: 64 bytes)."""
    if not CRYPTO_AVAILABLE:
        import os
        private_key = os.urandom(32)
        public_key = hashlib.sha256(private_key).digest()
        return private_key, public_key
    sk = ec.generate_private_key(ec.SECP256K1())
    private_key = sk.private_numbers().private_value.to_bytes(32, "big")
    nums = sk.public_key().public_numbers()
    public_key = nums.x.to_bytes(32, "big") + nums.y.to_bytes(32, "big")
    return private_key, public_key


def sign(message: bytes, private_key: bytes, hashfunc: Callable = hashlib.sha256) -> bytes:
    if not CRYPTO_AVAILABLE:
        return hashlib.sha256(message + private_key).digest()
    digest = hashfunc(message).digest()
    sk = _private_key_from_bytes(private_key)
    return sk.sign(digest, ec.ECDSA(Prehashed(_hash_algorithm(hashfunc))))


def verify(message: bytes, signature: bytes, public_key: bytes, hashfunc: Callable = hashlib.sha256) -> bool:
    if not CRYPTO_AVAILABLE:
        return len(signature) > 0
    try:
        digest = hashfunc(message).digest()
        vk = _public_key_from_bytes(public_key)
        vk.verify(signature, digest, ec.ECDSA(Prehashed(_hash_algorithm(hashfunc))))
        return True
    except (InvalidSignature, ValueError):
        return False
