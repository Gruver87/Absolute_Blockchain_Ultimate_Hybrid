#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SECP256K1 через cryptography (OpenSSL).
Замена python-ecdsa — CVE-2024-23342 (Minerva timing attack) без патча в ecdsa.
"""

import hashlib
from typing import Callable, Iterable, List, Tuple

from crypto import native

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
    from cryptography.hazmat.primitives import hashes
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    ec = None  # type: ignore
    Prehashed = None  # type: ignore
    hashes = None  # type: ignore
    InvalidSignature = Exception  # type: ignore

# Совместимость с прежним флагом
ECDSA_AVAILABLE = CRYPTO_AVAILABLE

_HASH_ALGO = (
    {
        hashlib.sha256: hashes.SHA256,
        hashlib.sha3_256: hashes.SHA3_256,
    }
    if CRYPTO_AVAILABLE
    else {}
)


def _require_backend() -> None:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("SECP256K1 backend not available")


def _hash_algorithm(hashfunc: Callable):
    _require_backend()
    return _HASH_ALGO.get(hashfunc, hashes.SHA256)()


def _private_key_from_bytes(private_key: bytes) -> "ec.EllipticCurvePrivateKey":
    _require_backend()
    return ec.derive_private_key(int.from_bytes(private_key, "big"), ec.SECP256K1())


def _public_key_from_bytes(public_key: bytes) -> "ec.EllipticCurvePublicKey":
    _require_backend()
    x = int.from_bytes(public_key[:32], "big")
    y = int.from_bytes(public_key[32:], "big")
    return ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1()).public_key()


def generate_keypair() -> tuple:
    """Returns (private_key: 32 bytes, public_key: 64 bytes)."""
    _require_backend()
    sk = ec.generate_private_key(ec.SECP256K1())
    private_key = sk.private_numbers().private_value.to_bytes(32, "big")
    nums = sk.public_key().public_numbers()
    public_key = nums.x.to_bytes(32, "big") + nums.y.to_bytes(32, "big")
    return private_key, public_key


def sign(message: bytes, private_key: bytes, hashfunc: Callable = hashlib.sha256) -> bytes:
    _require_backend()
    digest = hashfunc(message).digest()
    sk = _private_key_from_bytes(private_key)
    return sk.sign(digest, ec.ECDSA(Prehashed(_hash_algorithm(hashfunc))))


def verify(message: bytes, signature: bytes, public_key: bytes, hashfunc: Callable = hashlib.sha256) -> bool:
    if not CRYPTO_AVAILABLE:
        return False
    if hashfunc is hashlib.sha256:
        native_result = native.verify_secp256k1_sha256(message, signature, public_key)
        if native_result is not None:
            return native_result
    try:
        digest = hashfunc(message).digest()
        vk = _public_key_from_bytes(public_key)
        vk.verify(signature, digest, ec.ECDSA(Prehashed(_hash_algorithm(hashfunc))))
        return True
    except (InvalidSignature, ValueError):
        return False


def verify_batch_sha256(
    items: Iterable[Tuple[bytes, bytes, bytes]]
) -> List[bool]:
    """
    Batch verify DER ECDSA signatures over SHA256(message).

    Each item is (message, signature_der, public_key_xy). The function is
    fail-closed: malformed inputs produce False for that item.
    """
    batch = list(items)
    if not CRYPTO_AVAILABLE:
        return [False for _ in batch]

    native_result = native.verify_secp256k1_sha256_batch(batch)
    if native_result is not None:
        return native_result

    return [
        verify(message, signature, public_key, hashfunc=hashlib.sha256)
        for message, signature, public_key in batch
    ]
