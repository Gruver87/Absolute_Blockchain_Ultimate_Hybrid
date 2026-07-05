#!/usr/bin/env python3
"""Binary key encoding for RocksDB chain storage."""

from __future__ import annotations

import struct
from typing import Iterable, List, Tuple

# Column-family style single-DB prefixes
P_BLOCK_HEIGHT = b"\x01"
P_BLOCK_HASH = b"\x02"
P_BLOCK_TX = b"\x03"
P_TX = b"\x04"
P_TX_RECEIPT = b"\x05"
P_ACCOUNT = b"\x10"
P_VALIDATOR = b"\x20"
P_META = b"\x40"
P_BURN = b"\x41"
P_PROPOSER_AUDIT = b"\x42"
P_STATE_ROOT_MM = b"\x43"
P_TX_PROP = b"\x44"
P_TX_FROM = b"\x06"
P_TX_TO = b"\x07"
P_BRIDGE_LOCK = b"\x50"
P_BRIDGE_CREDIT = b"\x51"


def pack_u64(value: int) -> bytes:
    return struct.pack(">Q", int(value) & 0xFFFFFFFFFFFFFFFF)


def unpack_u64(data: bytes) -> int:
    if len(data) != 8:
        raise ValueError("invalid u64 key segment")
    return struct.unpack(">Q", data)[0]


def normalize_hash_key(block_hash: str) -> bytes:
    h = (block_hash or "").strip().lower()
    if h.startswith("0x"):
        h = h[2:]
    if len(h) != 64:
        raise ValueError(f"invalid block hash key: {block_hash!r}")
    return bytes.fromhex(h)


def key_block_height(height: int) -> bytes:
    return P_BLOCK_HEIGHT + pack_u64(height)


def key_block_hash_to_height(block_hash: str) -> bytes:
    return P_BLOCK_HASH + normalize_hash_key(block_hash)


def key_tx(tx_hash: str) -> bytes:
    h = (tx_hash or "").strip().lower()
    if h.startswith("0x"):
        h = h[2:]
    return P_TX + bytes.fromhex(h.zfill(64)[-64:])


def key_block_tx(height: int, tx_hash: str) -> bytes:
    return P_BLOCK_TX + pack_u64(height) + key_tx(tx_hash)[1:]


def _tx_hash_body(tx_hash: str) -> bytes:
    return key_tx(tx_hash)[len(P_TX) :]


def key_tx_from_index(address: str, block_height: int, tx_hash: str) -> bytes:
    return (
        P_TX_FROM
        + normalize_address_key(address).encode("utf-8")
        + pack_u64(int(block_height))
        + _tx_hash_body(tx_hash)
    )


def key_tx_to_index(address: str, block_height: int, tx_hash: str) -> bytes:
    return (
        P_TX_TO
        + normalize_address_key(address).encode("utf-8")
        + pack_u64(int(block_height))
        + _tx_hash_body(tx_hash)
    )


def prefix_tx_from(address: str) -> bytes:
    return P_TX_FROM + normalize_address_key(address).encode("utf-8")


def prefix_tx_to(address: str) -> bytes:
    return P_TX_TO + normalize_address_key(address).encode("utf-8")


def normalize_address_key(address: str) -> str:
    """Match SQLite Database._normalize_address (arbitrary labels allowed)."""
    return (address or "").strip().lower()


def key_account(address: str) -> bytes:
    # Genesis pools use symbolic keys (0xecosystem..., treasury, mining_pool).
    return P_ACCOUNT + normalize_address_key(address).encode("utf-8")


def key_validator(address: str) -> bytes:
    return P_VALIDATOR + normalize_address_key(address).encode("utf-8")


def key_meta(name: str) -> bytes:
    return P_META + name.encode("utf-8")


def key_burn(height: int) -> bytes:
    return P_BURN + pack_u64(height)


def key_proposer_audit(height: int) -> bytes:
    return P_PROPOSER_AUDIT + pack_u64(height)


def prefix_block_heights() -> bytes:
    return P_BLOCK_HEIGHT


def prefix_accounts() -> bytes:
    return P_ACCOUNT


def prefix_validators() -> bytes:
    return P_VALIDATOR


def iter_prefix_keys(rows: Iterable[Tuple[bytes, bytes]], prefix: bytes) -> List[Tuple[bytes, bytes]]:
    out: List[Tuple[bytes, bytes]] = []
    for key, value in rows:
        if not key.startswith(prefix):
            break
        out.append((key, value))
    return out
