import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# tests/unit/test_block.py
import pytest
from core.block import Block
from core.transaction import Transaction
import time

def test_create_block():
    txs = [
        Transaction("hash1", "alice", "bob", 100, 0.001, int(time.time()), 0),
        Transaction("hash2", "bob", "charlie", 50, 0.001, int(time.time()), 0)
    ]
    block = Block(
        height=1,
        previous_hash="0"*64,
        transactions=txs,
        timestamp=int(time.time()),
        nonce=0,
        miner="foundation"
    )
    assert block.height == 1
    assert len(block.merkle_root) == 64

def test_block_verify():
    txs = []
    block = Block(0, "0"*64, txs, int(time.time()), 0, "genesis")
    block.block_hash = block.calculate_hash()
    assert block.verify() == True




