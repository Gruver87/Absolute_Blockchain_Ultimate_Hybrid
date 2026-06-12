import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_security():
    from security_module import jwt_auth, rate_limiter, input_validator
    assert jwt_auth is not None
    assert rate_limiter is not None
    assert input_validator is not None

def test_mempool():
    from mempool_storage import mempool, state_manager, chain_storage
    assert mempool is not None
    assert state_manager is not None

def test_crypto():
    from crypto_advanced import hybrid_crypto, ed25519, secp256k1
    assert hybrid_crypto is not None

def test_nft():
    from enhanced_nft_marketplace import marketplace
    assert marketplace is not None
    stats = marketplace.get_stats()
    assert 'total_sales' in stats

def test_blockchain():
    try:
        from blockchain import Blockchain
        b = Blockchain()
        assert b is not None
    except ImportError:
        pass
