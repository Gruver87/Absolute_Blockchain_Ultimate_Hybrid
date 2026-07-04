#!/usr/bin/env python3
"""Tests for RLP + Ethereum raw transaction decode."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from crypto import native
from crypto.crypto import Crypto
from crypto.eth_tx import decode_raw_transaction, verify_eth_transaction_dict
from crypto.rlp import decode_single, encode
from crypto.secp256k1_backend import sign


def _build_signed_legacy(chain_id: int = 77777):
    priv_hex, pub_hex, addr = Crypto.generate_keypair()
    private_key = bytes.fromhex(priv_hex)
    nonce = 0
    gas_price = 1_000_000_000
    gas_limit = 21_000
    to_addr = bytes.fromhex("ab" * 20)
    value = 0
    data = b""
    signing_payload = [nonce, gas_price, gas_limit, to_addr, value, data, chain_id, b"", b""]
    signing_hash = native.keccak256_digest(encode(signing_payload))

    def _prehashed(_message: bytes):
        class _Digest:
            def digest(self):
                return signing_hash
        return _Digest()

    der = sign(signing_hash, private_key, hashfunc=_prehashed)
    r_int, s_int = decode_dss_signature(der)
    r = r_int.to_bytes(32, "big")
    s = s_int.to_bytes(32, "big")
    rec_id = None
    for candidate in (0, 1):
        recovered = native.recover_eth_address_keccak(signing_hash, r, s, candidate)
        if recovered.lower() == addr.lower():
            rec_id = candidate
            break
    assert rec_id is not None
    v = rec_id + 35 + 2 * chain_id
    signed = encode([nonce, gas_price, gas_limit, to_addr, value, data, v, r, s])
    return signed, addr, chain_id


def test_rlp_roundtrip_integers():
    payload = [0, 1, 255, 256]
    encoded = encode(payload)
    decoded = decode_single(encoded)
    assert decoded == [b"", b"\x01", b"\xff", b"\x01\x00"]


def test_decode_signed_legacy_transaction():
    raw, addr, chain_id = _build_signed_legacy()
    decoded = decode_raw_transaction(raw)
    assert decoded["from"].lower() == addr.lower()
    assert decoded["eth_signed"] is True
    assert decoded["chain_id"] == chain_id
    assert verify_eth_transaction_dict(decoded)


def test_difficulty_opcode_executes():
    from evm_interpreter import EVM, EVMContext
    ctx = EVMContext(difficulty=42)
    result = EVM(context=ctx).execute_bytecode(bytes([0x44, 0x00]))
    assert result["stack"][-1] == 42
