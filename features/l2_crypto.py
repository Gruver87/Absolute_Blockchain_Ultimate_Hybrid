"""Shared L2 cryptography — canonical state hashing and secp256k1 signatures."""

from __future__ import annotations

from crypto import native
import json
from typing import Any, Dict, Optional

from crypto.hashing import Hasher
from crypto.signing import Signer


def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def hash_state(payload: Dict[str, Any]) -> str:
    return Hasher.hash_object(json.loads(canonical_json(payload)))


def sign_state(payload: Dict[str, Any], private_key: bytes) -> str:
    return Signer._sign_hash(hash_state(payload), private_key)


def verify_state(payload: Dict[str, Any], signature_hex: str, public_key: bytes) -> bool:
    if not signature_hex or not public_key:
        return False
    try:
        sig = bytes.fromhex(signature_hex)
    except ValueError:
        return False
    return Signer._verify_hash(hash_state(payload), sig, public_key)


def payment_hash(preimage: str) -> str:
    return native.sha256_hex(preimage.encode("utf-8"))
