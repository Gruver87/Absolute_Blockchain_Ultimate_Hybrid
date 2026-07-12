#!/usr/bin/env python3
"""Block builder tx_root matches core blockchain Merkle rules."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.blockchain import Block, Transaction
from crypto.merkle import merkle_root
from execution.block_builder import BlockBuilder


class _FakeMempool:
    def get_sorted_transactions(self):
        return []


class _FakeState:
    def get_balance(self, _addr):
        return 0.0


def test_block_builder_empty_tx_root_matches_block():
    builder = BlockBuilder(_FakeMempool(), _FakeState())
    root = builder._compute_tx_root([])
    block = Block(height=1, parent_hash="0" * 64, miner="0x" + "1" * 40, transactions=[])
    assert root == block.tx_root == merkle_root(["empty"])


def test_block_builder_tx_root_matches_block():
    txs = [
        Transaction(
            from_addr="0x" + "a" * 40,
            to_addr="0x" + "b" * 40,
            value=1.0,
            nonce=0,
        ),
        Transaction(
            from_addr="0x" + "c" * 40,
            to_addr="0x" + "d" * 40,
            value=2.0,
            nonce=1,
        ),
    ]
    builder = BlockBuilder(_FakeMempool(), _FakeState())
    dict_txs = [{"hash": tx.hash} for tx in txs]
    root = builder._compute_tx_root(dict_txs)
    block = Block(height=2, parent_hash="0" * 64, miner="0x" + "1" * 40, transactions=txs)
    assert root == block.tx_root
