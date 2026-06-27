#!/usr/bin/env python3
"""HMAC auth for bridge relayer / oracle callbacks."""
import hashlib
import hmac
from typing import Optional


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    if not secret or not signature:
        return False
    expected = sign_payload(secret, body)
    return hmac.compare_digest(expected.strip().lower(), signature.strip().lower())
