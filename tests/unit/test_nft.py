import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# tests/unit/test_nft.py
import pytest
from modules.nft import NFTModule

def test_nft_collection():
    nft = NFTModule(None)
    collection_id = nft.create_collection("Test Collection", "foundation", 5)
    assert collection_id is not None

def test_nft_stats():
    nft = NFTModule(None)
    stats = nft.get_stats()
    assert "total_nfts" in stats



