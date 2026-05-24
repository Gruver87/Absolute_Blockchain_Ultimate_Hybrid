import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# tests/unit/test_crypto.py
import pytest
from core.wallet_crypto import CryptoWallet

def test_create_wallet():
    wallet = CryptoWallet.create_wallet()
    assert wallet["address"] is not None
    assert wallet["public_key"] is not None
    assert wallet["private_key"] is not None

def test_sign_and_verify():
    wallet = CryptoWallet.create_wallet()
    message = "Hello Blockchain"
    signature = CryptoWallet.sign_message(wallet["private_key"], message)
    assert CryptoWallet.verify_signature(wallet["public_key"], message, signature) == True



