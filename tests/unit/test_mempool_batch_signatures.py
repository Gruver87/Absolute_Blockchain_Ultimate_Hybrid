#!/usr/bin/env python3
"""Mempool native batch signature gate."""

from blockchain.mempool import Mempool, MempoolTransaction


def test_mempool_add_batch_uses_signature_batch(monkeypatch):
    mempool = Mempool()
    mempool.require_signatures = False

    calls = {"batch": 0, "single": 0}

    def _batch(txs):
        calls["batch"] += 1
        return [True for _ in txs]

    def _single(tx):
        calls["single"] += 1
        return True

    monkeypatch.setattr(
        "blockchain.mempool.verify_transaction_signatures_batch",
        _batch,
    )
    monkeypatch.setattr(
        "blockchain.mempool.verify_transaction_signature",
        _single,
    )

    txs = [
        MempoolTransaction("h1", "0x" + "1" * 40, "0x" + "2" * 40, 1.0, 0.01, signature="aa", public_key="bb" * 32),
        MempoolTransaction("h2", "0x" + "3" * 40, "0x" + "4" * 40, 2.0, 0.02, signature="cc", public_key="dd" * 32),
    ]
    added, rejected = mempool.add_batch(txs)
    assert added == 2
    assert rejected == 0
    assert calls["batch"] == 1
    assert calls["single"] == 0
