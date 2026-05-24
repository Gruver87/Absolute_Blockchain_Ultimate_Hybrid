import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# tests/unit/test_merkle.py
import pytest
from core.merkle import MerkleTree
from core.transaction import Transaction
import time

def test_merkle_root():
    txs = ["tx1", "tx2", "tx3"]
    root = MerkleTree.build_merkle_root(txs)
    assert len(root) == 64

def test_merkle_proof():
    txs = ["tx1", "tx2", "tx3", "tx4"]
    root = MerkleTree.build_merkle_root(txs)
    proof = MerkleTree.generate_proof("tx2", txs)
    assert MerkleTree.verify_proof("tx2", proof, root) == True




