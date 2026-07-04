#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consensus hashing parity for Rust-backed native facade."""

import hashlib

from blockchain.canonical_serializer import CanonicalSerializer
from core.block_header import BlockHeader
from core.blockchain import Block, Transaction
from crypto import native
from crypto.hashing import Hasher
from light.light_client import LightClient


def test_native_hash_text_matches_hashlib():
    payload = "absolute-consensus-hash:42"
    assert native.hash_text(payload) == hashlib.sha256(payload.encode()).hexdigest()


def test_native_hash_text_batch_matches_hashlib():
    payloads = [f"header-{i}" for i in range(8)]
    assert native.hash_text_batch(payloads) == [
        hashlib.sha256(payload.encode()).hexdigest()
        for payload in payloads
    ]


def test_native_validate_hash_chain_accepts_contiguous_links():
    headers = [
        (6, "0x06", "0x05"),
        (7, "0x07", "0x06"),
        (8, "0x08", "0x07"),
    ]
    assert native.validate_hash_chain(headers, expected_parent_hash="0x05", start_height=5)


def test_native_validate_hash_chain_rejects_broken_parent():
    headers = [
        (6, "0x06", "0x05"),
        (7, "0x07", "0xBAD"),
    ]
    assert not native.validate_hash_chain(headers, expected_parent_hash="0x05", start_height=5)


def test_transaction_hash_keeps_legacy_raw_format():
    tx = Transaction(
        "0x" + "a" * 40,
        "0x" + "b" * 40,
        1.25,
        nonce=7,
        gas=21000,
        data="0xdeadbeef",
        timestamp=123456,
    )
    raw = f"{tx.from_addr}{tx.to_addr}{tx.value}{tx.nonce}{tx.gas}{tx.data}{tx.timestamp}"
    assert tx.hash == hashlib.sha256(raw.encode()).hexdigest()


def test_block_header_hash_keeps_legacy_raw_format():
    header = BlockHeader(
        number=9,
        parent_hash="0" * 64,
        proposer="0x" + "c" * 40,
        state_root="1" * 64,
        tx_root="2" * 64,
        timestamp=987654,
        extra_data="prod",
    )
    raw = (
        f"{header.number}{header.parent_hash}{header.proposer}"
        f"{header.state_root}{header.tx_root}{header.timestamp}{header.extra_data}"
    )
    assert header.hash() == hashlib.sha256(raw.encode()).hexdigest()


def test_block_header_hash_matches_legacy_payload():
    header = BlockHeader(
        number=9,
        parent_hash="0" * 64,
        proposer="0x" + "c" * 40,
        state_root="1" * 64,
        tx_root="2" * 64,
        timestamp=987654,
        extra_data="prod",
    )
    assert native.block_header_hash(
        header.number,
        header.parent_hash,
        header.proposer,
        header.state_root,
        header.tx_root,
        header.timestamp,
        header.extra_data,
    ) == header.hash()


def test_block_header_hash_batch_matches_single_hashes():
    headers = [
        BlockHeader(
            number=i,
            parent_hash=str(i - 1).zfill(64),
            proposer="0x" + "a" * 40,
            state_root=str(i).zfill(64),
            tx_root=str(i + 1).zfill(64),
            timestamp=1000 + i,
            extra_data="batch",
        )
        for i in range(12)
    ]
    batch_input = [
        (
            h.number,
            h.parent_hash,
            h.proposer,
            h.state_root,
            h.tx_root,
            h.timestamp,
            h.extra_data,
        )
        for h in headers
    ]
    assert native.block_header_hash_batch(batch_input) == [h.hash() for h in headers]


def test_block_header_batch_hash_matches_single_hashes():
    parent = "0" * 64
    headers = []
    for i in range(12):
        header = BlockHeader(
            number=i,
            parent_hash=parent,
            proposer="0x" + "a" * 40,
            state_root=str(i).zfill(64),
            tx_root=str(i + 1).zfill(64),
            timestamp=1000 + i,
            extra_data="batch",
        )
        headers.append(header)
        parent = header.hash()
    assert BlockHeader.batch_hash(headers) == [header.hash() for header in headers]


def test_light_client_add_headers_uses_batch_hash_index():
    parent = "0" * 64
    headers = []
    for i in range(5):
        header = BlockHeader(
            number=i,
            parent_hash=parent,
            proposer="0x" + "b" * 40,
            state_root=str(i).zfill(64),
            tx_root=str(i + 1).zfill(64),
            timestamp=2000 + i,
        )
        headers.append(header)
        parent = header.hash()
    lc = LightClient()
    assert lc.add_headers(headers) == 5
    assert lc.add_headers(headers) == 0
    for header in headers:
        assert lc.header_by_hash[header.hash()] is header


def test_transaction_hash_native_matches_legacy_raw():
    tx = Transaction(
        "0x" + "a" * 40,
        "0x" + "b" * 40,
        1.25,
        nonce=7,
        gas=21000,
        data="0xdeadbeef",
        timestamp=123456,
    )
    assert native.transaction_hash(
        tx.from_addr,
        tx.to_addr,
        tx.value,
        tx.nonce,
        tx.gas,
        tx.data,
        tx.timestamp,
    ) == tx.hash


def test_block_canonical_hash_native_matches_block_hash():
    tx1 = Transaction("0xa", "0xb", 2.0, nonce=2, timestamp=100, tx_hash="b" * 64)
    tx2 = Transaction("0xc", "0xd", 3.0, nonce=3, timestamp=101, tx_hash="a" * 64)
    block = Block(
        height=4,
        parent_hash="0" * 64,
        miner="0x" + "e" * 40,
        transactions=[tx1, tx2],
        timestamp=777,
        extra_data="x",
        state_root="f" * 64,
    )
    block_dict = {
        "height": block.height,
        "parent_hash": block.parent_hash,
        "miner": block.miner,
        "timestamp": block.timestamp,
        "extra_data": block.extra_data,
        "state_root": block.state_root,
        "transactions": [
            {
                "hash": tx.hash,
                "from": tx.from_addr,
                "to": tx.to_addr,
                "amount": tx.value,
                "fee": tx.fee,
                "nonce": tx.nonce,
                "timestamp": tx.timestamp,
            }
            for tx in sorted(block.transactions, key=lambda t: t.hash)
        ],
    }
    assert native.block_canonical_hash(block_dict) == block.hash


def test_block_canonical_hash_keeps_serializer_format():
    tx1 = Transaction("0xa", "0xb", 2.0, nonce=2, timestamp=100, tx_hash="b" * 64)
    tx2 = Transaction("0xc", "0xd", 3.0, nonce=3, timestamp=101, tx_hash="a" * 64)
    block = Block(
        height=4,
        parent_hash="0" * 64,
        miner="0x" + "e" * 40,
        transactions=[tx1, tx2],
        timestamp=777,
        extra_data="x",
        state_root="f" * 64,
    )
    block_dict = {
        "height": block.height,
        "parent_hash": block.parent_hash,
        "miner": block.miner,
        "timestamp": block.timestamp,
        "extra_data": block.extra_data,
        "state_root": block.state_root,
        "transactions": [
            {
                "hash": tx.hash,
                "from": tx.from_addr,
                "to": tx.to_addr,
                "amount": tx.value,
                "fee": tx.fee,
                "nonce": tx.nonce,
                "timestamp": tx.timestamp,
            }
            for tx in sorted(block.transactions, key=lambda t: t.hash)
        ],
    }
    canonical = CanonicalSerializer.serialize(block_dict)
    assert block.hash == hashlib.sha256(canonical.encode()).hexdigest()


def test_hasher_hash_object_uses_same_canonical_json():
    obj = {"b": 2, "a": [3, {"x": "y"}]}
    encoded = b'{"a":[3,{"x":"y"}],"b":2}'
    assert Hasher.hash_object(obj) == hashlib.sha256(encoded).hexdigest()
