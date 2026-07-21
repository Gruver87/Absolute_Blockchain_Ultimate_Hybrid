#!/usr/bin/env python3
"""v1.3.42: native RocksDB key codec parity."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import abs_native

from crypto import native
from storage import keycodec


@contextmanager
def _python_keycodec_fallback():
    saved_native = keycodec._native
    saved_checked = keycodec._native_checked
    keycodec._native = None
    keycodec._native_checked = True
    try:
        yield
    finally:
        keycodec._native = saved_native
        keycodec._native_checked = saved_checked


def _fallback_result(function, *args):
    with _python_keycodec_fallback():
        return function(*args)


def test_native_rocks_keycodec_symbols():
    assert keycodec.native_keycodec_available()
    for symbol in (
        "rocks_pack_u64",
        "rocks_unpack_u64",
        "rocks_key_account",
        "rocks_key_block_height",
        "rocks_key_block_hash_to_height",
        "rocks_key_tx_recent_index",
        "rocks_key_evm_log",
        "rocks_key_nft_token",
    ):
        assert hasattr(abs_native, symbol)

    assert hasattr(native, "rocks_key_account")
    assert hasattr(native, "rocks_pack_u64")
    assert hasattr(native, "rocks_key_block_height")
    assert hasattr(native, "rocks_unpack_u64")


def test_pack_and_unpack_u64_native_matches_python():
    for value in (0, 1, 0x0123456789ABCDEF, 0xFFFFFFFFFFFFFFFF):
        native_packed = keycodec.pack_u64(value)
        assert native_packed == _fallback_result(keycodec.pack_u64, value)
        assert keycodec.unpack_u64(native_packed) == _fallback_result(
            keycodec.unpack_u64, native_packed
        )


def test_rocks_keys_native_match_python_fallback():
    tx_hash = "0x" + "ab" * 32
    block_hash = "0x" + "cd" * 32
    cases = (
        (keycodec.key_account, ("  Treasury_Pool  ",)),
        (keycodec.key_block_height, (123456789,)),
        (keycodec.key_block_hash_to_height, (block_hash,)),
        (keycodec.key_tx_recent_index, (321, 1_721_234_567, tx_hash)),
        (keycodec.key_evm_log, (321, tx_hash, 17)),
        (keycodec.key_nft_token, ("  nft:collection:0007  ",)),
    )
    for function, args in cases:
        assert function(*args) == _fallback_result(function, *args)


def test_keycodec_wiring_mentions_native_account_kernel():
    text = (ROOT / "storage" / "keycodec.py").read_text(encoding="utf-8")
    assert "rocks_key_account" in text
