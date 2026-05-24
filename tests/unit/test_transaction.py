import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# tests/unit/test_transaction.py
import pytest
from core.transaction import Transaction
import time

def test_create_transaction():
    tx = Transaction(
        tx_hash="test_hash",
        from_addr="alice",
        to_addr="bob",
        amount=100.0,
        fee=0.001,
        timestamp=int(time.time()),
        nonce=0
    )
    assert tx.from_addr == "alice"
    assert tx.to_addr == "bob"
    assert tx.amount == 100.0

def test_transaction_hash():
    tx = Transaction(
        tx_hash="",
        from_addr="alice",
        to_addr="bob",
        amount=100.0,
        fee=0.001,
        timestamp=1234567890,
        nonce=0
    )
    tx_hash = tx.calculate_hash()
    assert len(tx_hash) == 64




