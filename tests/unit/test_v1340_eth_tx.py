#!/usr/bin/env python3
"""v1.3.40: native eth raw tx decode kernel."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native
from crypto.eth_tx import decode_raw_transaction, verify_eth_transaction_dict
from tests.unit.test_eth_raw_tx import _build_signed_legacy, _build_signed_blob


def test_native_eth_tx_symbol():
    assert native.native_available()
    assert hasattr(native, "decode_eth_raw_tx")
    assert hasattr(native, "decode_eth_raw_tx_hex")


def test_native_decode_legacy_matches_python_path():
    raw, addr, chain_id = _build_signed_legacy()
    decoded = decode_raw_transaction(raw)
    assert decoded["from"].lower() == addr.lower()
    assert decoded["chain_id"] == chain_id
    assert decoded["eth_tx_type"] == "legacy"
    assert verify_eth_transaction_dict(decoded)
    # Direct kernel JSON
    import json

    direct = json.loads(native.decode_eth_raw_tx(raw))
    assert direct["from"].lower() == addr.lower()
    assert direct["eth_tx_type"] == "legacy"


def test_native_decode_eip4844():
    raw, addr, chain_id, blob_hash = _build_signed_blob()
    decoded = decode_raw_transaction(raw)
    assert decoded["from"].lower() == addr.lower()
    assert decoded["eth_tx_type"] == "eip4844"
    assert decoded["blob_versioned_hashes"] == ["0x" + blob_hash.hex()]
    assert decoded["blob_hashes"] == [int.from_bytes(blob_hash, "big")]
    assert verify_eth_transaction_dict(decoded)


def test_unsupported_typed_tx():
    try:
        decode_raw_transaction(b"\x01\xc0")
        assert False, "expected unsupported"
    except ValueError as exc:
        assert "unsupported_typed_tx" in str(exc)


def test_wiring():
    text = Path("crypto/eth_tx.py").read_text(encoding="utf-8")
    assert "decode_eth_raw_tx" in text
    assert "def decode_eth_raw_tx" in Path("crypto/native.py").read_text(encoding="utf-8")
