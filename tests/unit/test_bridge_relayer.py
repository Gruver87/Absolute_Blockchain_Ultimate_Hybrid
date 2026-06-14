#!/usr/bin/env python3
"""Bridge relayer worker tests."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from bridge.oracle_auth import sign_payload, verify_signature


def test_oracle_hmac_roundtrip():
    secret = "test-secret"
    body = json.dumps({"tx_hash": "0xabc"}).encode()
    sig = sign_payload(secret, body)
    assert verify_signature(secret, body, sig)
    assert not verify_signature(secret, body, "bad")


def test_relayer_module_imports():
    import importlib.util
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "scripts",
        "bridge_relayer.py",
    )
    spec = importlib.util.spec_from_file_location("bridge_relayer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "process_pending")
