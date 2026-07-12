#!/usr/bin/env python3
"""RLP native kernel parity with Python fallback."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crypto import native
from crypto.rlp import _python_decode, _python_encode, decode_single, encode


def _python_decode_single(data: bytes):
    item, end = _python_decode(data, 0)
    if end != len(data):
        raise ValueError("rlp_trailing_bytes")
    return item


@pytest.mark.skipif(not native.native_available(), reason="abs_native required")
def test_rlp_native_matches_python_reference():
    samples = [
        [0, 1, 255, 256],
        [b"", b"\x01", b"\xff"],
        [1_000_000_000, 21_000, bytes.fromhex("ab" * 20), 0, b""],
    ]
    for sample in samples:
        py_bytes = _python_encode(sample)
        native_bytes = encode(sample)
        assert native_bytes == py_bytes
        assert decode_single(native_bytes) == _python_decode_single(py_bytes)


def test_rlp_encode_empty_list():
    encoded = encode([])
    assert encoded == b"\xc0"
