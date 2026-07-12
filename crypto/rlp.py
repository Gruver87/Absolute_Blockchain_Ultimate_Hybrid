#!/usr/bin/env python3
"""Minimal RLP encode/decode for Ethereum transactions."""

from __future__ import annotations

from typing import List, Tuple, Union

RLPItem = Union[bytes, int, List["RLPItem"]]

_native = None
_native_error: Exception | None = None
try:
    import abs_native as _native_mod

    _native = _native_mod
except Exception as exc:  # pragma: no cover - import-time optional
    _native_error = exc


def _python_int_to_bytes(value: int) -> bytes:
    if value == 0:
        return b""
    length = (value.bit_length() + 7) // 8
    return value.to_bytes(length, "big")


def _python_normalize_item(item: RLPItem) -> bytes:
    if isinstance(item, list):
        return _python_encode(item)
    if isinstance(item, int):
        return _python_normalize_item(_python_int_to_bytes(item))
    if isinstance(item, bytes):
        data = item
    else:
        data = bytes(item)
    if len(data) == 1 and data[0] <= 0x7F:
        return data
    if not data:
        return b"\x80"
    if len(data) == 1 and data[0] < 0x80:
        return data
    return bytes([0x80 + len(data)]) + data


def _python_encode(item: RLPItem) -> bytes:
    if isinstance(item, list):
        payload = b"".join(_python_normalize_item(child) for child in item)
        if len(payload) <= 55:
            return bytes([0xC0 + len(payload)]) + payload
        len_bytes = _python_int_to_bytes(len(payload))
        return bytes([0xF7 + len(len_bytes)]) + len_bytes + payload
    return _python_normalize_item(item)


def _python_decode_length(data: bytes, pos: int, offset: int) -> Tuple[int, int]:
    if pos >= len(data):
        raise ValueError("rlp_truncated")
    prefix = data[pos]
    if prefix < offset + 0x37:
        return prefix - offset, pos + 1
    len_of_len = prefix - (offset + 0x37)
    start = pos + 1
    end = start + len_of_len
    if end > len(data):
        raise ValueError("rlp_truncated")
    length = int.from_bytes(data[start:end], "big")
    return length, end


def _python_decode(data: bytes, pos: int = 0) -> Tuple[RLPItem, int]:
    if pos >= len(data):
        raise ValueError("rlp_truncated")
    prefix = data[pos]
    if prefix <= 0x7F:
        return bytes([prefix]), pos + 1
    if prefix <= 0xB7:
        length = prefix - 0x80
        if length == 0:
            return b"", pos + 1
        start = pos + 1
        end = start + length
        if end > len(data):
            raise ValueError("rlp_truncated")
        return data[start:end], end
    if prefix <= 0xBF:
        length, next_pos = _python_decode_length(data, pos, 0x80)
        start = next_pos
        end = start + length
        if end > len(data):
            raise ValueError("rlp_truncated")
        return data[start:end], end
    if prefix <= 0xF7:
        length = prefix - 0xC0
        start = pos + 1
        end = start + length
        if end > len(data):
            raise ValueError("rlp_truncated")
        items: List[RLPItem] = []
        cursor = start
        while cursor < end:
            child, cursor = _python_decode(data, cursor)
            items.append(child)
        if cursor != end:
            raise ValueError("rlp_invalid_list")
        return items, end
    length, next_pos = _python_decode_length(data, pos, 0xC0)
    start = next_pos
    end = start + length
    if end > len(data):
        raise ValueError("rlp_truncated")
    items = []
    cursor = start
    while cursor < end:
        child, cursor = _python_decode(data, cursor)
        items.append(child)
    if cursor != end:
        raise ValueError("rlp_invalid_list")
    return items, end


def encode(item: RLPItem) -> bytes:
    if _native is not None and hasattr(_native, "rlp_encode"):
        return bytes(_native.rlp_encode(item))
    return _python_encode(item)


def decode(data: bytes, pos: int = 0) -> Tuple[RLPItem, int]:
    if _native is not None and hasattr(_native, "rlp_decode"):
        item, end = _native.rlp_decode(data, pos)
        return item, int(end)
    return _python_decode(data, pos)


def decode_single(data: bytes) -> RLPItem:
    if _native is not None and hasattr(_native, "rlp_decode_single"):
        return _native.rlp_decode_single(data)
    item, end = _python_decode(data, 0)
    if end != len(data):
        raise ValueError("rlp_trailing_bytes")
    return item


def item_to_int(item: RLPItem) -> int:
    if isinstance(item, int):
        return item
    if isinstance(item, list):
        raise ValueError("rlp_expected_scalar")
    if not item:
        return 0
    return int.from_bytes(item, "big")
