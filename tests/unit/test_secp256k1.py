#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crypto.secp256k1_backend import CRYPTO_AVAILABLE, generate_keypair, sign, verify


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_sign_verify_roundtrip():
    private_key, public_key = generate_keypair()
    message = b"absolute-blockchain-test"
    sig = sign(message, private_key, hashfunc=hashlib.sha256)
    assert verify(message, sig, public_key, hashfunc=hashlib.sha256)
    assert not verify(b"tampered", sig, public_key, hashfunc=hashlib.sha256)
