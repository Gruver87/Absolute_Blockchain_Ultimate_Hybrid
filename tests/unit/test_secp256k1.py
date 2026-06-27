#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crypto.secp256k1_backend import (
    CRYPTO_AVAILABLE,
    generate_keypair,
    sign,
    verify,
    verify_batch_sha256,
)


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_sign_verify_roundtrip():
    private_key, public_key = generate_keypair()
    message = b"absolute-blockchain-test"
    sig = sign(message, private_key, hashfunc=hashlib.sha256)
    assert verify(message, sig, public_key, hashfunc=hashlib.sha256)
    assert not verify(b"tampered", sig, public_key, hashfunc=hashlib.sha256)


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_batch_verify_matches_single_verify():
    private_key, public_key = generate_keypair()
    messages = [b"absolute-tx-1", b"absolute-tx-2", b"absolute-tx-3"]
    signatures = [
        sign(message, private_key, hashfunc=hashlib.sha256)
        for message in messages
    ]

    batch = [
        (message, signature, public_key)
        for message, signature in zip(messages, signatures)
    ]
    batch.append((b"tampered", signatures[0], public_key))

    assert verify_batch_sha256(batch) == [True, True, True, False]


def test_secp_backend_fails_closed_when_unavailable(monkeypatch):
    import crypto.secp256k1_backend as backend

    monkeypatch.setattr(backend, "CRYPTO_AVAILABLE", False)

    with pytest.raises(RuntimeError):
        backend.generate_keypair()
    with pytest.raises(RuntimeError):
        backend.sign(b"message", b"1" * 32)
    assert backend.verify(b"message", b"signature", b"public") is False
    assert backend.verify_batch_sha256([(b"message", b"signature", b"public")]) == [False]


def test_key_wallet_and_signer_fail_closed_when_unavailable(monkeypatch):
    import crypto.keys as keys
    import crypto.signing as signing
    import crypto.wallet as wallet

    monkeypatch.setattr(keys, "ECDSA_AVAILABLE", False)
    monkeypatch.setattr(wallet, "ECDSA_AVAILABLE", False)
    monkeypatch.setattr(signing, "ECDSA_AVAILABLE", False)

    with pytest.raises(RuntimeError):
        keys.KeyGenerator.private_to_public(b"1" * 32)
    with pytest.raises(RuntimeError):
        wallet.Wallet.create_new()
    with pytest.raises(RuntimeError):
        signing.Signer._sign_hash("a" * 64, b"1" * 32)
