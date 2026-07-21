#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rust-backed peer chain validation and Keccak-256 parity."""

import pytest

from core.block_header import BlockHeader
from core.blockchain import Block, Transaction
from crypto import native
from light.light_client import LightClient


def test_keccak256_empty_vector():
    assert native.keccak256_hex(b"") == (
        "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    )


def test_validate_imported_block_chain_accepts_valid_blocks():
    tx = Transaction("0xa", "0xb", 1.0, nonce=1, timestamp=10)
    block = Block(
        height=2,
        parent_hash="p" * 64,
        miner="0x" + "1" * 40,
        transactions=[tx],
        timestamp=100,
        state_root="s" * 64,
    )
    assert native.validate_imported_block_chain(
        [block.to_dict()],
        expected_parent_hash="p" * 64,
        start_height=1,
    )


def test_validate_imported_block_chain_rejects_tampered_hash():
    tx = Transaction("0xa", "0xb", 1.0, nonce=1, timestamp=10)
    block = Block(
        height=2,
        parent_hash="p" * 64,
        miner="0x" + "1" * 40,
        transactions=[tx],
        timestamp=100,
        state_root="s" * 64,
    )
    bad = block.to_dict()
    bad["hash"] = "0" * 64
    assert not native.validate_imported_block_chain(
        [bad],
        expected_parent_hash="p" * 64,
        start_height=1,
    )


def test_validate_peer_header_chain_accepts_contiguous_headers():
    parent = "0" * 64
    headers = []
    for i in range(3):
        header = BlockHeader(
            number=i,
            parent_hash=parent,
            proposer="0x" + "a" * 40,
            state_root=str(i).zfill(64),
            tx_root=str(i + 1).zfill(64),
            timestamp=1000 + i,
        )
        headers.append(header)
        parent = header.hash()
    payload = [
        (
            h.number,
            h.hash(),
            h.parent_hash,
            h.proposer,
            h.state_root,
            h.tx_root,
            h.timestamp,
            h.extra_data,
        )
        for h in headers
    ]
    assert native.validate_peer_header_chain(
        payload,
        expected_parent_hash="0" * 64,
        start_height=-1,
    )


def test_light_client_rejects_broken_peer_header_chain():
    good = BlockHeader(
        number=1,
        parent_hash="0" * 64,
        proposer="0x" + "b" * 40,
        state_root="1" * 64,
        tx_root="2" * 64,
        timestamp=50,
    )
    bad = BlockHeader(
        number=2,
        parent_hash="BAD" + "0" * 61,
        proposer="0x" + "c" * 40,
        state_root="3" * 64,
        tx_root="4" * 64,
        timestamp=51,
    )
    lc = LightClient()
    assert lc.add_headers([good]) == 1
    assert lc.add_headers([bad]) == 0


def test_native_validate_imported_block_chain_rejects_too_many_blocks():
    if not native.native_available():
        return
    import abs_native

    payload = ['{"height":1}'] * 20_001
    with pytest.raises(ValueError, match="too_many_blocks"):
        abs_native.validate_imported_block_chain(payload, "", 0)


def test_native_validate_imported_block_chain_rejects_huge_block_json():
    if not native.native_available():
        return
    import abs_native

    huge = "{" + ('"x":' + '"' + ("a" * (2 * 1024 * 1024)) + '"') + "}"
    with pytest.raises(ValueError, match="block_json_too_large"):
        abs_native.validate_imported_block_chain([huge], "", 0)


def test_native_validate_peer_header_chain_rejects_too_many_headers():
    if not native.native_available():
        return
    import abs_native

    headers = [(1, "h" * 64, "p" * 64, "0x" + "a" * 40, "s" * 64, "t" * 64, 1, "")] * 20_001
    with pytest.raises(ValueError, match="too_many_headers"):
        abs_native.validate_peer_header_chain(headers, "", 0)
