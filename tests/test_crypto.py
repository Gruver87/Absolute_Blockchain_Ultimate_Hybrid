# tests/test_crypto.py
import pytest

def test_crypto():
    from crypto_advanced import hybrid_crypto
    assert hybrid_crypto is not None
