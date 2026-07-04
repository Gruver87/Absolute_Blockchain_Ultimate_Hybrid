#!/usr/bin/env python3
"""Native batch hash wrappers and bridge production gates."""

from crypto import native


def test_block_canonical_hash_batch_matches_single():
    block = {
        "height": 2,
        "parent_hash": "p" * 64,
        "miner": "0x" + "1" * 40,
        "timestamp": 100,
        "extra_data": "v1",
        "state_root": "s" * 64,
        "transactions": [{"hash": "tx1", "from": "0xa", "to": "0xb", "amount": 1, "fee": 0, "nonce": 0, "timestamp": 1}],
    }
    single = native.block_canonical_hash(block)
    batch = native.block_canonical_hash_batch([block, block])
    assert batch == [single, single]


def test_keccak256_digest_batch_matches_single():
    items = [b"", b"absolute", b"bridge"]
    singles = [native.keccak256_digest(item) for item in items]
    batch = native.keccak256_digest_batch(items)
    assert batch == singles
