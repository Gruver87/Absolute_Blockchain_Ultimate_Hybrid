# tests/test_nft.py
import pytest

def test_nft_manager():
    from nft_core import NFTManager
    nft = NFTManager()
    assert nft is not None
